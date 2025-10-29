"""
青云对象存储客户端
参考文档：https://docsv4.qingcloud.com/user_guide/storage/object_storage/sdk/python/
"""
import os
import uuid

# 注意：避免与本地 qingstor_api 包冲突，使用完整的导入路径
from qingstor.sdk.service.qingstor import QingStor
from qingstor.sdk.config import Config

# 代理配置
from utils.proxy import ProxyManager


class QingStorClient:
    """青云对象存储客户端"""
    
    def __init__(self, access_key_id: str, secret_access_key: str, zone: str = 'pek3a', proxy_manager_ref=None):
        """
        初始化青云对象存储客户端
        
        Args:
            access_key_id: 访问密钥 ID
            secret_access_key: 访问密钥 Secret
            zone: 区域，默认 pek3a（北京3区A）
            proxy_manager_ref: 代理管理器引用
        """
        self.config = Config(access_key_id, secret_access_key)
        self.service = QingStor(self.config)
        self.zone = zone
        self.bucket_name = 'tmp'
        self.proxy_manager = proxy_manager_ref
    
    def upload_file_from_url(self, url: str, bucket: str = None) -> dict:
        """
        从 URL 下载文件并上传到对象存储
        
        注意：下载外部文件可以使用代理，但上传到青云不使用代理
        
        Args:
            url: 文件 URL
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
        
        try:
            # 配置代理（下载外部文件可能使用代理）
            proxies = None
            if self.proxy_manager:
                proxies = self.proxy_manager.get_proxy_for_url(url)
            
            # 下载文件
            response = requests.get(url, timeout=30, stream=True, proxies=proxies)
            response.raise_for_status()
            
            # 如果使用代理，显示提示
            if proxies:
                print(f"🔗 通过代理下载文件: {url}")
            
            # 获取文件名
            filename = self._get_filename_from_url(url, response.headers)
            
            # 读取文件内容
            file_content = response.content
            file_size = len(file_content)
            
            # 生成唯一文件名
            file_id = str(uuid.uuid4())
            ext = Path(filename).suffix if '.' in filename else ''
            object_key = f"{file_id}{ext}"
            
            # 初始化桶
            qingstor_bucket = self.service.Bucket(bucket, self.zone)
            
            # 上传文件到青云（不使用代理）
            # 注意：青云对象存储的上传操作不走代理，确保直连
            output = qingstor_bucket.put_object(
                object_key,
                body=io.BytesIO(file_content)
            )
            
            print(f"📤 直连上传到青云对象存储: {bucket}/{object_key}")
            
            if output.status_code not in [200, 201]:
                raise Exception(f"上传失败，状态码: {output.status_code}")
            
            # 构造文件 URL（青云对象存储的 URL 格式）
            # 青云对象存储的 URL 格式：https://<bucket>.<zone>.qingstor.com/<object_key>
            file_url = f"https://{bucket}.{self.zone}.qingstor.com/{object_key}"
            
            return {
                'success': True,
                'filename': filename,
                'url': file_url,
                'size': file_size,
                'bucket': bucket,
                'object_key': object_key
            }
            
        except requests.RequestException as e:
            return {
                'success': False,
                'error': f"下载文件失败: {str(e)}"
            }
        except Exception as e:
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
        # 尝试从 Content-Disposition 头获取文件名
        if 'Content-Disposition' in headers:
            import re
            match = re.search(r'filename="?([^";]+)"?', headers['Content-Disposition'])
            if match:
                return match.group(1)
        
        # 从 URL 中提取文件名
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        filename = os.path.basename(unquote(parsed.path))
        
        # 如果文件名无效，生成一个默认名称
        if not filename or '.' not in filename:
            # 尝试从 Content-Type 推断扩展名
            content_type = headers.get('Content-Type', 'application/octet-stream')
            ext_map = {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'application/pdf': '.pdf',
                'application/zip': '.zip',
                'text/plain': '.txt'
            }
            ext = ext_map.get(content_type, '.bin')
            filename = f"download{ext}"
        
        return filename
    

