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
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# 导入企业微信官方 SDK
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'weworkapi_python-master', 'callback_python3'))
from WXBizMsgCrypt import WXBizMsgCrypt
import xml.etree.ElementTree as ET
from wechat.api import WeChatAPI
from github_api.api import GitHubAPI
from utils.locks import TaskLock
from qingstor_api.client import QingStorClient

# 加载环境变量
load_dotenv()

# 导入代理管理器
from utils.proxy import ProxyManager

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
        wx_api.send_text_message(user_id, content)
    except Exception as e:
        app.logger.error(f"发送消息失败: {str(e)}")


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


def handle_url_upload(user_id: str, url: str) -> bool:
    """
    处理 URL 上传
    
    Args:
        user_id: 用户 ID
        url: 文件 URL
        
    Returns:
        是否处理成功
    """
    if qingstor_client is None:
        send_response(
            user_id,
            "❌ 青云对象存储未配置\n\n请在 .env 文件中配置以下变量：\n"
            "- QINGSTOR_ACCESS_KEY_ID\n"
            "- QINGSTOR_SECRET_ACCESS_KEY\n"
            "- QINGSTOR_ZONE (可选)"
        )
        return False
    
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
            return True
        else:
            # 发送失败消息
            send_response(
                user_id,
                f"❌ 文件上传失败\n\n错误: {result.get('error', '未知错误')}"
            )
            return False
            
    except Exception as e:
        app.logger.error(f"上传文件失败: {str(e)}")
        send_response(user_id, f"❌ 处理失败: {str(e)}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})


@app.route('/wechat/callback', methods=['GET', 'POST'])
def wechat_callback():
    """企业微信回调接口"""
    if request.method == 'GET':
        # 回调验证
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        echostr = request.args.get('echostr')
        
        if not all([msg_signature, timestamp, nonce, echostr]):
            return '缺少参数', 400
        
        try:
            ret, result = wx_crypt.VerifyURL(msg_signature, timestamp, nonce, echostr)
            if ret != 0:
                return '验证失败', 400
            return result, 200
        except Exception as e:
            app.logger.error(f"验证失败: {str(e)}")
            return '验证失败', 400
    
    else:
        # 接收消息
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        
        if not all([msg_signature, timestamp, nonce]):
            return '缺少参数', 400
        
        try:
            # 解密消息
            ret, xml_content = wx_crypt.DecryptMsg(
                request.get_data().decode('utf-8'),
                msg_signature,
                timestamp,
                nonce
            )
            
            if ret != 0:
                raise Exception(f"解密失败，错误码: {ret}")
            
            # 解析解密后的消息
            tree = ET.fromstring(xml_content)
            msg_type = tree.find('MsgType').text
            
            # 只处理文本消息
            if msg_type != 'text':
                return 'success', 200
            
            user_id = tree.find('FromUserName').text
            content_node = tree.find('Content')
            content = content_node.text if content_node is not None else ''
            content = content.strip()
            
            # 第一步：检测是否是 URL（优先处理）
            if is_url(content):
                handle_url_upload(user_id, content)
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
            
            # 检查任务锁
            if task_lock.is_locked():
                send_response(user_id, "⏳ 已有任务正在处理中，请稍后再试")
                return 'success', 200
            
            # 获取锁
            if not task_lock.acquire():
                send_response(user_id, "❌ 获取任务锁失败")
                return 'success', 200
            
            try:
                # 格式化镜像名称
                images = [format_image_name(img) for img in images]
                
                # 发送确认消息
                msg_lines = [f"🔄 正在处理镜像同步请求...\n共 {len(images)} 个镜像："]
                namespace = os.getenv('DOCKER_NAMESPACE', 'namespace')
                registry = os.getenv('DOCKER_REGISTRY', 'registry.cn-hangzhou.aliyuncs.com')
                
                for i, image in enumerate(images, 1):
                    # 解析镜像名
                    if ':' in image:
                        img_name, img_tag = image.split(':', 1)
                    else:
                        img_name, img_tag = image, 'latest'
                    
                    # 获取镜像路径部分
                    img_path = img_name.split('/')[-1]
                    target_image = f"{registry}/{namespace}/{img_path}:{img_tag}"
                    msg_lines.append(f"{i}. {image} → {target_image}")
                
                send_response(user_id, '\n'.join(msg_lines))
                
                # 更新 GitHub
                success = github_api.append_images(images)
                
                if success:
                    # 触发 GitHub Actions
                    github_api.trigger_action()
                    
                    # 发送成功消息
                    send_response(
                        user_id,
                        f"✅ 镜像同步任务已提交！\n\n共 {len(images)} 个镜像已添加到同步队列\n\n请查看 GitHub Actions 了解同步进度"
                    )
                else:
                    send_response(user_id, "❌ 更新 GitHub 失败")
                
            finally:
                # 释放锁
                task_lock.release()
            
            return 'success', 200
            
        except Exception as e:
            app.logger.error(f"处理消息失败: {str(e)}")
            return f'处理失败: {str(e)}', 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)

