"""
青云对象存储客户端
"""
import uuid
import logging
logger = logging.getLogger(__name__)

try:
    from qingstor.sdk.service.qingstor import QingStor
    from qingstor.sdk.config import Config
except ImportError as e:
    logger.error(f"导入青云 SDK 失败: {e}")
    raise


class QingStorClient:
    """青云对象存储客户端"""
    
    def __init__(self, access_key_id: str, secret_access_key: str, zone: str = 'pek3a', bucket: str = None, proxy_manager_ref=None):
        """
        初始化青云对象存储客户端
        
        Args:
            access_key_id: 访问密钥 ID
            secret_access_key: 访问密钥
            zone: 区域，默认 pek3a
            bucket: 存储桶名称，默认从环境变量 QINGSTOR_BUCKET 读取，否则为 'tmp'
            proxy_manager_ref: 代理管理器引用（用于依赖注入）
        """
        import os
        self.config = Config(access_key_id, secret_access_key)
        self.service = QingStor(self.config)
        self.zone = zone
        # 从参数或环境变量获取 bucket 名称，默认 'tmp'
        self.bucket_name = bucket or os.getenv('QINGSTOR_BUCKET', 'tmp')
        self.proxy_manager = proxy_manager_ref
    
    def upload_file_from_url(self, url: str, bucket: str = None) -> dict:
        """
        从 URL 下载文件并上传到青云对象存储
        
        根据文件大小选择策略：
        - 小文件（< 100MB）：直接内存上传，更快
        - 大文件（≥ 100MB）：保存到本地，流式上传，节省内存
        
        Args:
            url: 文件的 HTTPS 链接
            bucket: 存储桶名称，默认 tmp
            
        Returns:
            上传结果，包含文件 URL 和文件名
        """
        import requests
        import io
        from pathlib import Path
        
        # 确定桶名称
        if bucket is None:
            bucket = self.bucket_name
        
        # 文件大小阈值：100MB
        SIZE_THRESHOLD = 100 * 1024 * 1024  # 100MB
        
        local_file_path = None
        upload_body = None
        use_file_storage = False
        
        try:
            # 配置代理（下载外部文件可能使用代理）
            proxies = None
            if self.proxy_manager:
                proxies = self.proxy_manager.get_proxy_for_url(url)
            
            # 先发送 HEAD 请求获取文件大小
            logger.info(f"📥 检测文件信息: {url}")
            try:
                head_response = requests.head(url, timeout=10, proxies=proxies, allow_redirects=True)
                content_length = head_response.headers.get('Content-Length')
                
                if content_length:
                    file_size = int(content_length)
                    if file_size >= SIZE_THRESHOLD:
                        use_file_storage = True
                        logger.info(f"📦 大文件检测（{file_size / 1024 / 1024:.2f}MB），将使用本地存储并流式上传")
                    else:
                        logger.info(f"📦 小文件检测（{file_size / 1024 / 1024:.2f}MB），将使用内存直接上传")
                else:
                    # 无法获取大小，默认使用本地存储（保守策略）
                    use_file_storage = True
                    logger.info("⚠️  无法获取文件大小（无 Content-Length），将使用本地存储并流式上传")
            except Exception as e:
                # HEAD 请求失败，使用保守策略
                use_file_storage = True
                logger.warning(f"⚠️  文件大小检测失败: {str(e)}，将使用本地存储并流式上传")
            
            # 下载文件
            logger.info(f"📥 开始下载文件: {url}")
            if proxies:
                logger.info(f"🔗 通过代理下载文件: {url}")
            
            response = requests.get(url, timeout=30, stream=True, proxies=proxies)
            response.raise_for_status()
            
            # 获取文件名
            filename = self._get_filename_from_url(url, response.headers)
            
            # 清理文件名（移除可能的安全风险字符）
            safe_filename = self._sanitize_filename(filename)
            
            if use_file_storage:
                # 大文件：保存到本地
                tmp_dir = Path('tmp')
                tmp_dir.mkdir(exist_ok=True)
                local_file_path = tmp_dir / safe_filename
                
                logger.info(f"💾 保存文件到本地: {local_file_path}")
                file_size = 0
                with open(local_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            file_size += len(chunk)
                
                logger.info(f"✅ 文件下载完成 - 大小: {file_size / 1024 / 1024:.2f}MB, 保存路径: {local_file_path}")
                # 文件对象，用于流式上传
                upload_body = open(local_file_path, 'rb')
            else:
                # 小文件：直接读取到内存
                logger.info("💾 读取文件到内存")
                file_content = response.content
                file_size = len(file_content)
                logger.info(f"✅ 文件下载完成 - 大小: {file_size / 1024 / 1024:.2f}MB")
                upload_body = io.BytesIO(file_content)
            
            # 使用原始文件名作为 object_key（与本地文件名一致）
            object_key = safe_filename
            
            # 初始化桶
            qingstor_bucket = self.service.Bucket(bucket, self.zone)
            
            logger.info(f"访问密钥ID: {self.config.access_key_id[:10]}...")
            
            # 检查 bucket 是否存在，不存在则创建
            try:
                head_output = qingstor_bucket.head()
                logger.info(f"✅ Bucket '{bucket}' 存在")
            except Exception as head_error:
                # bucket 不存在，尝试创建
                error_str = str(head_error)
                if '404' in error_str or 'Not Found' in error_str or 'not exist' in error_str.lower():
                    logger.info(f"⚠️  Bucket '{bucket}' 不存在，尝试创建...")
                    try:
                        # 创建 bucket
                        # 青云 SDK 创建 bucket 的方式：调用 put() 方法
                        logger.debug(f"调用 qingstor_bucket.put() 创建 bucket...")
                        put_bucket_output = qingstor_bucket.put()
                        put_status = getattr(put_bucket_output, 'status_code', None) or getattr(put_bucket_output, 'status', None)
                        
                        logger.debug(f"Bucket 创建响应: {type(put_bucket_output)}, 状态码: {put_status}")
                        
                        if put_status in [200, 201]:
                            logger.info(f"✅ Bucket '{bucket}' 创建成功")
                        elif put_status == 409:
                            logger.info(f"ℹ️  Bucket '{bucket}' 已存在（409 冲突）")
                        else:
                            logger.warning(f"⚠️  Bucket 创建返回状态码: {put_status}，继续尝试上传")
                    except Exception as create_error:
                        error_msg = str(create_error)
                        # 409 表示 bucket 已存在，这是正常的
                        if '409' in error_msg or 'Conflict' in error_msg or 'already exists' in error_msg.lower():
                            logger.info(f"ℹ️  Bucket '{bucket}' 已存在（创建时返回冲突）")
                        else:
                            logger.warning(f"⚠️  Bucket 创建失败: {error_msg}，继续尝试上传（可能已存在）")
                else:
                    logger.warning(f"⚠️  Bucket 验证失败: {str(head_error)}，继续尝试上传")
            
            # 上传文件到青云（不使用代理）
            # 注意：青云对象存储的上传操作不走代理，确保直连
            logger.info(f"📤 准备上传到青云对象存储 - 桶: {bucket}, 区域: {self.zone}, 对象: {object_key}, 文件大小: {file_size / 1024 / 1024:.2f}MB")
            
            # 使用流式上传（upload_body 可能是文件对象或内存对象）
            output = qingstor_bucket.put_object(
                object_key,
                body=upload_body
            )
            
            # 如果是文件对象，需要关闭
            if use_file_storage and hasattr(upload_body, 'close'):
                upload_body.close()
            
            # 检查响应（青云 SDK 返回的是一个响应对象）
            # 青云 SDK 的响应通常有 status_code 属性
            status_code = None
            if hasattr(output, 'status_code'):
                status_code = output.status_code
            elif hasattr(output, 'status'):
                status_code = output.status
            
            # 打印响应的详细信息用于调试
            logger.debug(f"上传响应对象类型: {type(output)}")
            logger.debug(f"上传响应属性: {dir(output)}")
            
            if status_code is None:
                # 如果没有 status_code，可能需要通过其他方式判断
                logger.warning("⚠️  无法获取响应状态码，假设上传成功")
                logger.info(f"📤 上传到青云对象存储: {bucket}/{object_key}")
            else:
                logger.info(f"📤 上传到青云对象存储: {bucket}/{object_key}, 响应状态码: {status_code}")
                
                if status_code not in [200, 201]:
                    # 获取详细错误信息
                    error_details = []
                    
                    # 检查各种可能的错误信息属性
                    if hasattr(output, 'content'):
                        error_details.append(f"响应内容: {output.content}")
                    if hasattr(output, 'headers'):
                        error_details.append(f"响应头: {output.headers}")
                    if hasattr(output, 'text'):
                        error_details.append(f"响应文本: {output.text}")
                    
                    error_msg = ", ".join(error_details) if error_details else str(output)
                    logger.error(f"上传失败 - 状态码: {status_code}, 错误详情: {error_msg}")
                    
                    # 404 通常表示 bucket 不存在或区域配置错误
                    if status_code == 404:
                        raise Exception(
                            f"上传失败（404）\n"
                            f"可能的原因：\n"
                            f"1. Bucket '{bucket}' 不存在，请检查青云控制台\n"
                            f"2. 区域 '{self.zone}' 配置错误\n"
                            f"3. 访问密钥权限不足\n"
                            f"请确认 .env 中的 QINGSTOR_ZONE 配置正确"
                        )
                    else:
                        raise Exception(f"上传失败，状态码: {status_code}, 错误: {error_msg}")
            
            # 构造文件 URL（青云对象存储的 URL 格式）
            # 青云对象存储的 URL 格式：https://<bucket>.<zone>.qingstor.com/<object_key>
            file_url = f"https://{bucket}.{self.zone}.qingstor.com/{object_key}"
            
            result = {
                'success': True,
                'filename': filename,
                'url': file_url,
                'size': file_size,
                'bucket': bucket,
                'object_key': object_key
            }
            
            # 只有保存到本地的文件才返回 local_path
            if use_file_storage and local_file_path:
                result['local_path'] = str(local_file_path)
                # 可选：上传成功后删除本地文件（取消注释以启用）
                # local_file_path.unlink()
                # logger.info(f"🗑️  已删除本地临时文件: {local_file_path}")
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"下载文件失败: {url}, 错误: {str(e)}")
            # 确保文件对象被关闭
            if upload_body and hasattr(upload_body, 'close'):
                try:
                    upload_body.close()
                except:
                    pass
            return {
                'success': False,
                'error': f"下载文件失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"上传文件失败: url={url}, bucket={bucket}, zone={self.zone}, 错误: {str(e)}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            # 确保文件对象被关闭
            if upload_body and hasattr(upload_body, 'close'):
                try:
                    upload_body.close()
                except:
                    pass
            return {
                'success': False,
                'error': f"上传文件失败: {str(e)}"
            }
    
    def _get_filename_from_url(self, url: str, headers: dict) -> str:
        """
        从 URL 和响应头中提取文件名
        
        Args:
            url: 文件 URL
            headers: HTTP 响应头
            
        Returns:
            文件名
        """
        import re
        from urllib.parse import urlparse, unquote
        
        # 1. 尝试从 Content-Disposition 头获取
        content_disposition = headers.get('Content-Disposition', '')
        if content_disposition:
            match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
            if match:
                filename = match.group(1).strip('\'"')
                return unquote(filename)
        
        # 2. 从 URL 路径中提取
        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = path.split('/')[-1]
        
        if filename and '.' in filename:
            return filename
        
        # 3. 如果都没有，返回默认文件名
        return 'download'
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除可能的安全风险字符，但保留基本名称
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        import re
        from urllib.parse import unquote
        
        # URL 解码
        filename = unquote(filename)
        
        # 移除路径分隔符和危险字符（但保留文件名允许的字符）
        # 保留：字母、数字、点号、连字符、下划线、空格
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
        
        # 移除开头的点和空格（防止隐藏文件或空格问题）
        filename = filename.lstrip('. ')
        
        # 如果清理后为空，使用默认名称
        if not filename:
            filename = 'download'
        
        return filename
