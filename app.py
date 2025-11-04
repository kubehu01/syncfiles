"""
主应用：企业微信 Docker 镜像同步服务

参考文档：
- 企业微信 API: https://developer.work.weixin.qq.com/devtool/introduce
- 回调接口: https://developer.work.weixin.qq.com/document/path/90930
- 青云对象存储: https://docsv4.qingcloud.com/user_guide/storage/object_storage/sdk/python/
"""
import os
import re
import sys
import threading
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# 导入企业微信官方 SDK
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'weworkapi_python-master', 'callback_python3'))
from WXBizMsgCrypt import WXBizMsgCrypt
import xml.etree.ElementTree as ET
# 加载环境变量（最优先）
load_dotenv()

# 日志级别配置（可通过环境变量 LOG_LEVEL 配置，默认 INFO）
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
DEFAULT_LOG_LEVEL = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO)

# 配置日志（在其他导入之前，确保日志系统先初始化）
def setup_logging():
    """配置日志，同时输出到文件和控制台"""
    # 创建日志目录
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # 日志文件路径
    log_file = log_dir / 'app.log'
    
    # 配置日志格式
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(DEFAULT_LOG_LEVEL)
    
    # 清除已有的处理器（包括可能存在的默认处理器）
    root_logger.handlers = []
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(DEFAULT_LOG_LEVEL)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（支持轮转，最大10MB，保留5个备份）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(DEFAULT_LOG_LEVEL)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    logging.info(f"日志级别设置为: {LOG_LEVEL} ({DEFAULT_LOG_LEVEL})")
    
    # Flask/Werkzeug 日志配置 - 禁用 werkzeug 的日志输出
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)  # 只显示警告和错误
    werkzeug_logger.handlers = []
    werkzeug_logger.propagate = False  # 不传播，完全禁用输出

# 先初始化日志系统（在导入其他模块之前）
setup_logging()

# 现在安全导入其他模块（日志系统已初始化）
from utils.proxy import ProxyManager
from wechat.api import WeChatAPI
from github_api.api import GitHubAPI
from utils.locks import TaskLock
from qingstor_api.client import QingStorClient

app = Flask(__name__)

# 显示代理配置（启用检测）
proxy_manager = ProxyManager(check_availability=True)
if proxy_manager.is_proxy_enabled():
    app.logger.info(f"代理已启用: {proxy_manager.proxy_url}")
elif proxy_manager.proxy_url and not proxy_manager.available:
    app.logger.warning(f"代理不可用: {proxy_manager.proxy_url}，将使用非代理模式")
else:
    app.logger.info("未配置代理")

# 初始化组件
wx_crypt = WXBizMsgCrypt(
    os.getenv('TOKEN'),
    os.getenv('ENCODING_AES_KEY'),
    os.getenv('CORP_ID')
)

wx_api = WeChatAPI(
    corp_id=os.getenv('CORP_ID'),
    agent_id=os.getenv('AGENT_ID'),
    secret=os.getenv('SECRET')
)

github_api = GitHubAPI(
    token=os.getenv('GITHUB_TOKEN'),
    repo=os.getenv('GITHUB_REPO'),
    branch=os.getenv('GITHUB_BRANCH', 'main'),
    proxy_manager_ref=proxy_manager
)

# 初始化青云对象存储客户端（可选）
qingstor_client = None
if os.getenv('QINGSTOR_ACCESS_KEY_ID'):
    qingstor_client = QingStorClient(
        access_key_id=os.getenv('QINGSTOR_ACCESS_KEY_ID'),
        secret_access_key=os.getenv('QINGSTOR_SECRET_ACCESS_KEY'),
        zone=os.getenv('QINGSTOR_ZONE', 'pek3a'),
        bucket=os.getenv('QINGSTOR_BUCKET'),  # None 时会从环境变量读取或使用默认值
        proxy_manager_ref=proxy_manager
    )

task_lock = TaskLock()


def parse_image_list(content: str) -> list:
    """
    解析镜像列表
    
    Args:
        content: 消息内容
        
    Returns:
        镜像名称列表
    """
    images = []
    
    # 按换行分割
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # 处理逗号分隔的多个镜像
        for item in line.split(','):
            item = item.strip()
            if item:
                images.append(item)
    
    return images


def format_image_name(image: str) -> str:
    """
    格式化镜像名称
    
    Args:
        image: 镜像名称
        
    Returns:
        格式化后的镜像名称
    """
    # 移除平台架构参数（如 --platform=linux/amd64）
    image = re.sub(r'--platform=\S+', '', image).strip()
    return image


def send_response(user_id: str, content: str):
    """
    发送企业微信响应
    
    Args:
        user_id: 用户 ID
        content: 消息内容
    """
    try:
        app.logger.info(f"发送消息给用户 - 用户: {user_id}, 内容长度: {len(content)} 字符")
        app.logger.info(f"消息内容: {content}")
        wx_api.send_text_message(user_id, content)
        app.logger.info(f"消息发送成功 - 用户: {user_id}")
    except Exception as e:
        app.logger.error(f"发送消息失败 - 用户: {user_id}, 错误: {str(e)}")


def monitor_workflow_status(user_id: str, images: list, timeout: int = 600):
    """
    监控 GitHub Actions 工作流状态
    
    Args:
        user_id: 用户 ID
        images: 镜像列表
        timeout: 超时时间（秒）
    """
    def check_status():
        start_time = time.time()
        workflow_url = ""
        last_status = None
        
        while time.time() - start_time < timeout:
            # 等待一段时间再检查
            time.sleep(30)
            
            try:
                run_info = github_api.get_latest_workflow_run()
                
                if not run_info:
                    continue
                
                status = run_info['status']
                conclusion = run_info.get('conclusion')
                html_url = run_info['html_url']
                workflow_url = html_url
                
                # 如果状态发生变化，记录日志
                if status != last_status:
                    last_status = status
                    app.logger.info(f"Workflow 状态: {status}, 结论: {conclusion}")
                
                # 检查是否完成
                if status == 'completed':
                    if conclusion == 'success':
                        # 成功
                        success_msg = (
                            f"🎉 镜像同步成功！\n\n"
                            f"共 {len(images)} 个镜像已同步完成\n"
                            f"查看详情: {html_url}"
                        )
                        send_response(user_id, success_msg)
                        break
                    else:
                        # 失败
                        failure_msg = (
                            f"❌ 镜像同步失败\n\n"
                            f"共 {len(images)} 个镜像同步出错\n"
                            f"请查看日志排查问题\n"
                            f"查看详情: {html_url}"
                        )
                        send_response(user_id, failure_msg)
                        break
            
            except Exception as e:
                app.logger.error(f"检查 workflow 状态失败: {str(e)}")
        
        # 超时提示
        if time.time() - start_time >= timeout:
            timeout_msg = (
                f"⏰ 镜像同步超时\n\n"
                f"未能在 {timeout // 60} 分钟内完成同步\n"
                f"请手动查看进度: {workflow_url if workflow_url else 'GitHub Actions'}"
            )
            send_response(user_id, timeout_msg)
    
    # 启动后台线程监控
    thread = threading.Thread(target=check_status, daemon=True)
    thread.start()


# 用于去重的字典：记录正在处理的请求（用户ID+内容 -> 时间戳）
_processing_requests = {}
_processing_lock = threading.Lock()
REQUEST_DEDUP_INTERVAL = 5  # 5秒内相同请求只处理一次


def is_url(content: str) -> bool:
    """
    检测是否是 URL
    
    规则：
    - 以 http:// 或 https:// 开头
    - 不包含换行符（单行URL）
    
    Args:
        content: 消息内容
        
    Returns:
        是否是 URL
    """
    url_pattern = r'^https?://[^\s]+$'
    return bool(re.match(url_pattern, content.strip()))


def handle_image_sync_async(user_id: str, images: list):
    """
    异步处理镜像同步（后台线程）
    
    Args:
        user_id: 用户 ID
        images: 镜像列表
    """
    # 尝试获取锁（原子操作，避免竞态条件）
    if not task_lock.acquire():
        send_response(user_id, "⏳ 已有任务正在处理中，请稍后再试")
        return
    
    try:
        # 格式化镜像名称（移除平台参数等）
        source_images = [format_image_name(img) for img in images]
        
        # 发送确认消息
        msg_lines = [f"🔄 正在处理镜像同步请求...\n共 {len(source_images)} 个镜像："]
        namespace = os.getenv('DOCKER_NAMESPACE', 'namespace')
        registry = os.getenv('DOCKER_REGISTRY', 'registry.cn-hangzhou.aliyuncs.com')
        
        # 构建工作流需要的格式：<源镜像> to <目标镜像>:<标签>
        workflow_images = []
        
        for i, source_image in enumerate(source_images, 1):
            # 解析源镜像名
            if ':' in source_image:
                img_name, img_tag = source_image.split(':', 1)
            else:
                img_name, img_tag = source_image, 'latest'
            
            # 获取镜像路径部分
            img_path = img_name.split('/')[-1]
            target_image = f"{registry}/{namespace}/{img_path}:{img_tag}"
            
            # 构建工作流格式：源镜像 to 目标镜像:标签
            workflow_format = f"{source_image} to {target_image}"
            workflow_images.append(workflow_format)
            
            msg_lines.append(f"{i}. {source_image} → {target_image}")
        
        send_response(user_id, '\n'.join(msg_lines))
        
        # 更新 GitHub（先清空再写入，只同步本次镜像）
        success = github_api.append_images(workflow_images)
        
        if success:
            # 启动后台监控任务（会发送最终的成功/失败消息）
            # 传入源镜像列表用于显示
            monitor_workflow_status(user_id, source_images)
        else:
            send_response(user_id, "❌ 更新 GitHub 失败")
        
    except Exception as e:
        app.logger.error(f"处理镜像同步失败: {str(e)}")
        send_response(user_id, f"❌ 处理失败: {str(e)}")
    finally:
        # 释放锁
        task_lock.release()


def handle_url_upload_async(user_id: str, url: str):
    """
    异步处理 URL 上传（后台线程）
    
    Args:
        user_id: 用户 ID
        url: 文件 URL
    """
    if qingstor_client is None:
        send_response(
            user_id,
            "❌ 青云对象存储未配置\n\n请在 .env 文件中配置以下变量：\n"
            "- QINGSTOR_ACCESS_KEY_ID\n"
            "- QINGSTOR_SECRET_ACCESS_KEY\n"
            "- QINGSTOR_ZONE (可选)"
        )
        return
    
    try:
        # 发送开始消息
        send_response(user_id, f"📥 开始下载文件...\n\nURL: {url}")
        
        # 上传文件
        result = qingstor_client.upload_file_from_url(url)
        
        if result.get('success'):
            # 发送成功消息
            send_response(
                user_id,
                f"✅ 文件上传成功！\n\n"
                f"文件名: {result['filename']}\n"
                f"文件大小: {result['size']} 字节\n"
                f"存储桶: {result['bucket']}\n"
                f"下载链接: {result['url']}"
            )
        else:
            # 发送失败消息
            send_response(
                user_id,
                f"❌ 文件上传失败\n\n错误: {result.get('error', '未知错误')}"
            )
            
    except Exception as e:
        app.logger.error(f"上传文件失败: {str(e)}")
        send_response(user_id, f"❌ 处理失败: {str(e)}")


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})


@app.route('/wechat/callback', methods=['GET', 'POST'])
def wechat_callback():
    """企业微信回调接口"""
    # 记录请求信息
    app.logger.info("=" * 60)
    app.logger.info(f"收到企业微信回调请求: {request.method}")
    app.logger.info(f"请求路径: {request.path}")
    app.logger.debug(f"请求参数: {dict(request.args)}")
    
    if request.method == 'GET':
        # 回调验证
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        echostr = request.args.get('echostr')
        
        app.logger.debug(f"URL验证请求 - 签名: {msg_signature[:20] if msg_signature else 'None'}..., 时间戳: {timestamp}, 随机数: {nonce}, EchoStr: {echostr[:50] if echostr else 'None'}...")
        
        if not all([msg_signature, timestamp, nonce, echostr]):
            app.logger.warning("URL验证失败: 缺少必要参数")
            return '缺少参数', 400
        
        try:
            ret, result = wx_crypt.VerifyURL(msg_signature, timestamp, nonce, echostr)
            if ret != 0:
                app.logger.error(f"URL验证失败，错误码: {ret}")
                return '验证失败', 400
            app.logger.info("URL验证成功")
            return result, 200
        except Exception as e:
            app.logger.error(f"URL验证异常: {str(e)}")
            return '验证失败', 400
    
    else:
        # 接收消息
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        
        # 记录请求体（加密内容）
        try:
            post_data = request.get_data(as_text=True)
            app.logger.debug(f"消息请求 - 签名: {msg_signature[:20] if msg_signature else 'None'}..., 时间戳: {timestamp}, 随机数: {nonce}")
            app.logger.debug(f"加密消息体长度: {len(post_data)} 字符")
            app.logger.debug(f"加密消息体: {post_data[:200]}..." if len(post_data) > 200 else f"加密消息体: {post_data}")
        except Exception as e:
            app.logger.warning(f"读取请求体失败: {str(e)}")
        
        if not all([msg_signature, timestamp, nonce]):
            app.logger.warning("消息接收失败: 缺少必要参数")
            return '缺少参数', 400
        
        try:
            # 解密消息
            post_data = request.get_data().decode('utf-8')
            ret, xml_content = wx_crypt.DecryptMsg(
                post_data,
                msg_signature,
                timestamp,
                nonce
            )
            
            if ret != 0:
                app.logger.error(f"消息解密失败，错误码: {ret}")
                raise Exception(f"解密失败，错误码: {ret}")
            
            app.logger.debug("消息解密成功")
            app.logger.debug(f"解密后的消息内容: {xml_content}")
            
            # 解析解密后的消息
            tree = ET.fromstring(xml_content)
            msg_type = tree.find('MsgType').text
            
            app.logger.debug(f"消息类型: {msg_type}")
            
            # 只处理文本消息
            if msg_type != 'text':
                app.logger.info(f"跳过非文本消息: {msg_type}")
                return 'success', 200
            
            user_id = tree.find('FromUserName').text
            content_node = tree.find('Content')
            content = content_node.text if content_node is not None else ''
            content = content.strip()
            
            app.logger.info(f"收到用户消息 - 用户: {user_id}, 内容: {content}")
            
            # 去重检查：避免短时间内重复处理相同请求
            current_time = time.time()
            request_key = f"{user_id}:{content}"
            
            with _processing_lock:
                if request_key in _processing_requests:
                    last_time = _processing_requests[request_key]
                    if current_time - last_time < REQUEST_DEDUP_INTERVAL:
                        app.logger.info(f"跳过重复请求: {content} (上次处理时间: {current_time - last_time:.1f}秒前)")
                        return 'success', 200
                
                # 记录处理时间
                _processing_requests[request_key] = current_time
                
                # 清理过期的记录（超过去重间隔的记录）
                expired_keys = [
                    k for k, t in _processing_requests.items()
                    if current_time - t > REQUEST_DEDUP_INTERVAL
                ]
                for k in expired_keys:
                    del _processing_requests[k]
            
            # 第一步：检测是否是 URL（优先处理）
            if is_url(content):
                # 立即返回，在后台异步处理文件上传
                thread = threading.Thread(
                    target=handle_url_upload_async,
                    args=(user_id, content),
                    daemon=True
                )
                thread.start()
                return 'success', 200
            
            # 第二步：尝试解析为 Docker 镜像
            images = parse_image_list(content)
            
            if not images:
                # 无法识别，返回帮助信息
                send_response(
                    user_id,
                    "❌ 无法识别你的请求\n\n"
                    "支持的功能：\n"
                    "1️⃣  Docker 镜像同步：发送镜像名称\n"
                    "   例如：nginx:latest\n\n"
                    "2️⃣  文件下载上传：发送 HTTPS 链接\n"
                    "   例如：https://example.com/file.pdf"
                )
                return 'success', 200
            
            # 立即返回，在后台异步处理镜像同步
            thread = threading.Thread(
                target=handle_image_sync_async,
                args=(user_id, images),
                daemon=True
            )
            thread.start()
            return 'success', 200
            
        except Exception as e:
            app.logger.error(f"处理消息失败: {str(e)}")
            return f'处理失败: {str(e)}', 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)



