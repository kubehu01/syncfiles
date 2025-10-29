"""
代理配置管理
"""
import os
import requests
from typing import Optional, Dict
from urllib.parse import urlparse

# 延迟获取 logger，避免在模块导入时初始化
def _get_logger():
    import logging
    return logging.getLogger(__name__)


class ProxyManager:
    """代理管理器"""
    
    def __init__(self, check_availability: bool = True):
        """
        初始化代理管理器
        
        Args:
            check_availability: 是否检测代理可用性
        """
        self.proxy_url = os.getenv('PROXY_URL')
        self.no_proxy_domains = os.getenv('NO_PROXY_DOMAINS', '').split(',')
        self.no_proxy_domains = [domain.strip() for domain in self.no_proxy_domains if domain.strip()]
        self.available = True
        
        # 检测到代理时显示提示
        if self.proxy_url:
            _get_logger().info(f"🌐 检测到代理配置: {self.proxy_url}")
            if self.no_proxy_domains:
                _get_logger().info(f"  直连域名: {', '.join(self.no_proxy_domains)}")
            
            # 检测代理可用性
            if check_availability:
                self.available = self.check_proxy_availability()
    
    def should_use_proxy(self, url: str) -> bool:
        """
        判断 URL 是否需要使用代理
        
        Args:
            url: 目标 URL
            
        Returns:
            是否使用代理
        """
        # 没有配置代理，直接返回 False
        if not self.proxy_url:
            return False
        
        # 没有配置直连列表，所有请求都走代理
        if not self.no_proxy_domains:
            return True
        
        # 解析 URL
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            
            if not host:
                return True
            
            # 检查是否在直连列表中
            for domain in self.no_proxy_domains:
                # 完全匹配或域名结尾匹配
                if host == domain or host.endswith(f'.{domain}'):
                    return False
            
            return True
        except Exception:
            # 解析失败，使用代理
            return True
    
    def get_proxy_for_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        获取 URL 的代理配置
        
        Args:
            url: 目标 URL
            
        Returns:
            代理配置字典，格式如 {'http': 'http://proxy:port', 'https': 'http://proxy:port'}
            如果不需要代理或代理不可用则返回 None
        """
        # 如果代理不可用，直接返回 None
        if not self.available:
            return None
            
        if not self.should_use_proxy(url):
            return None
        
        # 返回代理配置
        return {
            'http': self.proxy_url,
            'https': self.proxy_url
        }
    
    def is_proxy_enabled(self) -> bool:
        """
        检查是否启用了代理
        
        Returns:
            是否启用了代理
        """
        return self.proxy_url is not None and self.available
    
    def check_proxy_availability(self) -> bool:
        """
        检测代理是否可用
        
        通过访问 Google 检测
        
        Returns:
            代理是否可用
        """
        if not self.proxy_url:
            return False
        
        try:
            proxies = {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
            
            # 访问 Google 进行检测
            response = requests.get(
                'https://www.google.com',
                proxies=proxies,
                timeout=5
            )
            
            if response.status_code == 200:
                _get_logger().info(f"✅ 代理可用: {self.proxy_url}")
                return True
            else:
                _get_logger().warning(f"⚠️  代理访问返回非 200 状态码: {response.status_code}")
                return False
                
        except requests.exceptions.ProxyError:
            _get_logger().warning(f"⚠️  代理连接失败: {self.proxy_url}\n   将使用非代理模式继续运行")
            return False
        except requests.exceptions.Timeout:
            _get_logger().warning(f"⚠️  代理连接超时: {self.proxy_url}\n   将使用非代理模式继续运行")
            return False
        except Exception as e:
            _get_logger().warning(f"⚠️  代理检测失败: {str(e)}\n   将使用非代理模式继续运行")
            return False


