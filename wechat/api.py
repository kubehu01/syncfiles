"""
企业微信 API 客户端
"""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WeChatAPI:
    """企业微信 API 客户端"""
    
    def __init__(self, corp_id: str, agent_id: str, secret: str):
        """
        初始化企业微信 API 客户端
        
        Args:
            corp_id: 企业 ID
            agent_id: 应用 ID
            secret: 应用密钥
        """
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.secret = secret
        self.base_url = 'https://qyapi.weixin.qq.com'
        self.access_token = None
        self.token_expires_at = 0
    
    def _get_access_token(self) -> str:
        """
        获取访问令牌
        
        Returns:
            访问令牌
        """
        import time
        
        # 如果 token 未过期，直接返回
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        # 获取新的 token
        url = f'{self.base_url}/cgi-bin/gettoken'
        params = {
            'corpid': self.corp_id,
            'corpsecret': self.secret
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errcode') != 0:
                error_msg = data.get('errmsg', '未知错误')
                if data.get('errcode') == 60020:
                    error_msg = f"IP 不在白名单: {error_msg}\n\n请在企业微信管理后台配置服务器 IP 白名单，或关闭 IP 白名单限制。\n更多信息: https://open.work.weixin.qq.com/devtool/query?e=60020"
                raise Exception(f"获取 access_token 失败: {error_msg}")
            
            self.access_token = data['access_token']
            # 提前 5 分钟过期，避免边界情况
            self.token_expires_at = time.time() + data.get('expires_in', 7200) - 300
            
            return self.access_token
            
        except requests.RequestException as e:
            raise Exception(f"请求 access_token 失败: {str(e)}")
    
    def send_text_message(self, user_id: str, content: str) -> bool:
        """
        发送文本消息
        
        Args:
            user_id: 用户 ID（企业微信用户 ID）
            content: 消息内容
            
        Returns:
            是否发送成功
        """
        try:
            access_token = self._get_access_token()
            url = f'{self.base_url}/cgi-bin/message/send'
            params = {'access_token': access_token}
            
            data = {
                'touser': user_id,
                'msgtype': 'text',
                'agentid': self.agent_id,
                'text': {
                    'content': content
                }
            }
            
            response = requests.post(url, params=params, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('errcode') != 0:
                error_msg = result.get('errmsg', '未知错误')
                if result.get('errcode') == 60020:
                    error_msg = f"IP 不在白名单: {error_msg}\n\n请在企业微信管理后台配置服务器 IP 白名单，或关闭 IP 白名单限制。\n更多信息: https://open.work.weixin.qq.com/devtool/query?e=60020"
                raise Exception(f"发送消息失败: {error_msg}")
            
            return True
            
        except requests.RequestException as e:
            raise Exception(f"发送消息失败: {str(e)}")


