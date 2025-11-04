"""
代理管理
"""
import os
import logging
import requests
from typing import Optional, Dict

# 延迟导入日志，避免循环依赖
def _get_logger():
    return logging.getLogger(__name__)


class ProxyManager:
    """代理管理器"""
    
    def __init__(self, check_availability: bool = False):
        """
        初始化代理管理器
        
        Args:
            check_availability: 是否检查代理可用性
        """
        self.proxy_url = os.getenv('PROXY_URL', '').strip()
        no_proxy_domains_str = os.getenv('NO_PROXY_DOMAINS', '').strip()
        self.no_proxy_domains = [d.strip() for d in no_proxy_domains_str.split(',') if d.strip()] if no_proxy_domains_str else []
        self.available = True  # 默认可用
        
        if self.proxy_url and check_availability:
            self.check_proxy_availability()
    
    def should_use_proxy(self, url: str) -> bool:
        """
        判断是否应该使用代理
        
        Args:
            url: 目标 URL
            
        Returns:
            是否应该使用代理
        """
        if not self.proxy_url or not self.available:
            return False
        
        # 检查是否在不使用代理的域名列表中
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.split(':')[0]  # 移除端口
        
        for no_proxy_domain in self.no_proxy_domains:
            if domain.endswith(no_proxy_domain) or no_proxy_domain.endswith(domain):
                return False
        
        return True
    
    def get_proxy_for_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        获取指定 URL 的代理配置
        
        Args:
            url: 目标 URL
            
        Returns:
            代理配置字典，如果不需要代理则返回 None
        """
        if not self.should_use_proxy(url):
            return None
        
        # 根据代理 URL 格式返回对应的代理配置
        if self.proxy_url.startswith('http://') or self.proxy_url.startswith('https://'):
            return {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
        elif self.proxy_url.startswith('socks5://'):
            return {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
        
        return None
    
    def is_proxy_enabled(self) -> bool:
        """
        检查是否启用了代理
        
        Returns:
            是否启用代理
        """
        return bool(self.proxy_url) and self.available
    
    def check_proxy_availability(self):
        """
        检查代理是否可用（通过访问 https://www.google.com 测试）
        """
        if not self.proxy_url:
            self.available = False
            return
        
        logger = _get_logger()
        
        try:
            proxies = self.get_proxy_for_url('https://www.google.com')
            if not proxies:
                # 不需要代理（可能在NO_PROXY列表中）
                self.available = True
                return
            
            response = requests.get(
                'https://www.google.com',
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                self.available = True
                logger.info(f"✅ 代理可用: {self.proxy_url}")
            else:
                self.available = False
                logger.warning(f"⚠️ 代理不可用: {self.proxy_url} (状态码: {response.status_code})")
        except Exception as e:
            self.available = False
            logger.warning(f"⚠️ 代理不可用: {self.proxy_url}，将使用非代理模式。错误: {str(e)}")


