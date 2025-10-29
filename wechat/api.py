"""
企业微信 API 客户端
参考官方文档：https://developer.work.weixin.qq.com/document/path/90236
"""
import requests
import time
from typing import Optional, Dict


class WeChatAPI:
    """企业微信 API 客户端"""
    
    def __init__(self, corp_id: str, agent_id: str, secret: str):
        """
        初始化
        
        Args:
            corp_id: 企业 ID
            agent_id: 应用 ID
            secret: 应用密钥
        """
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.secret = secret
        self.access_token = None
        self.token_expires_at = 0
    
    def _get_access_token(self) -> str:
        """
        获取 Access Token（带缓存）
        
        Returns:
            Access Token
        """
        # 检查缓存是否有效
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        # 请求新的 Token
        url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
        params = {
            'corpid': self.corp_id,
            'corpsecret': self.secret
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errcode') != 0:
                raise Exception(f"获取 Token 失败: {data.get('errmsg')}")
            
            self.access_token = data['access_token']
            # 提前 200 秒过期，避免边界问题
            self.token_expires_at = time.time() + data.get('expires_in', 7200) - 200
            
            return self.access_token
            
        except Exception as e:
            raise Exception(f"获取 Access Token 失败: {str(e)}")
    
    def send_text_message(self, user_id: str, content: str) -> bool:
        """
        发送文本消息
        
        参考文档：https://developer.work.weixin.qq.com/document/path/90236
        
        Args:
            user_id: 用户 ID（@all 表示全员）
            content: 消息内容
            
        Returns:
            是否发送成功
        """
        url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send'
        access_token = self._get_access_token()
        
        data = {
            'touser': user_id,
            'msgtype': 'text',
            'agentid': int(self.agent_id),
            'text': {
                'content': content
            }
        }
        
        try:
            response = requests.post(
                f'{url}?access_token={access_token}',
                json=data,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get('errcode') != 0:
                raise Exception(f"发送消息失败: {result.get('errmsg')}")
            
            return True
            
        except Exception as e:
            raise Exception(f"发送消息失败: {str(e)}")
    
