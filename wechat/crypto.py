"""
企业微信消息加解密模块
参考官方文档：https://developer.work.weixin.qq.com/document/path/90930
"""
import base64
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import xml.etree.ElementTree as ET
import os


class WXBizMsgCrypt:
    """企业微信消息加解密类"""
    
    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        """
        初始化
        
        Args:
            token: 企业微信 Token
            encoding_aes_key: 43 字节的 AES 密钥
            corp_id: 企业 ID
        """
        self.token = token
        self.corp_id = corp_id
        self.key = base64.b64decode(encoding_aes_key + '=')
        self.iv = self.key[:16]
    
    def _get_random_str(self):
        """生成随机字符串"""
        return base64.b64encode(os.urandom(16)).decode('utf-8')
    
    def _sha1(self, *args):
        """SHA1 哈希"""
        sha = hashlib.sha1()
        for arg in args:
            sha.update(arg.encode('utf-8'))
        return sha.hexdigest()
    
    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str):
        """
        验证回调 URL
        
        Args:
            msg_signature: 消息签名
            timestamp: 时间戳
            nonce: 随机数
            echostr: 加密的随机字符串
            
        Returns:
            解密后的随机字符串
        """
        # 计算签名
        sign = self._sha1(self.token, timestamp, nonce, echostr)
        
        if sign != msg_signature:
            raise Exception("签名验证失败")
        
        # 解密 echostr
        result, msg_len = self._decode(echostr)
        return result[:msg_len]
    
    def decrypt_msg(self, msg_signature: str, timestamp: str, nonce: str, post_data: str):
        """
        解密消息
        
        Args:
            msg_signature: 消息签名
            timestamp: 时间戳
            nonce: 随机数
            post_data: 加密的消息数据
            
        Returns:
            解密后的消息内容
        """
        # 解析 XML
        tree = ET.fromstring(post_data)
        encrypt_msg = tree.find('Encrypt').text
        to_user_name = tree.find('ToUserName').text
        
        # 计算签名
        sign = self._sha1(self.token, timestamp, nonce, encrypt_msg)
        
        # 调试输出
        print(f"[DEBUG] 签名验证:")
        print(f"  收到的签名: {msg_signature}")
        print(f"  计算的签名: {sign}")
        print(f"  Token: {self.token[:10]}...")
        print(f"  时间戳: {timestamp}")
        print(f"  随机数: {nonce}")
        
        if sign != msg_signature:
            raise Exception(f"签名验证失败: 期望 {sign}, 实际 {msg_signature}")
        
        # 解密消息
        result, msg_len = self._decode(encrypt_msg)
        msg_content = result[:msg_len]
        
        # 解析解密后的消息
        tree = ET.fromstring(msg_content)
        return {
            'ToUserName': tree.find('ToUserName').text,
            'FromUserName': tree.find('FromUserName').text,
            'CreateTime': tree.find('CreateTime').text,
            'MsgType': tree.find('MsgType').text,
            'Content': tree.find('Content').text if tree.find('Content') is not None else None,
            'MsgId': tree.find('MsgId').text if tree.find('MsgId') is not None else None
        }
    
    def _decode(self, text: str):
        """
        解密文本
        
        Args:
            text: Base64 编码的加密文本
            
        Returns:
            (解密后的内容, 内容长度)
        """
        try:
            # Base64 解码
            enc_data = base64.b64decode(text)
            
            # AES 解密
            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
            decrypted = cipher.decrypt(enc_data)
            
            # 移除 PKCS7 填充
            plain_text = unpad(decrypted, AES.block_size)
            
            # 企业微信消息格式：[4字节网络字节序的包长度][16字节的随机数][消息体][企业ID]
            # 提取内容长度（前4字节，网络字节序）
            content_len = int.from_bytes(plain_text[:4], byteorder='big')
            
            # 提取消息内容（跳过16字节随机数，取指定长度）
            if len(plain_text) < 16 + content_len:
                raise Exception(f"消息长度不足: 期望至少 {16 + content_len} 字节，实际 {len(plain_text)} 字节")
            
            content = plain_text[16:16 + content_len].decode('utf-8')
            
            return content, content_len
            
        except Exception as e:
            raise Exception(f"解密失败: {str(e)}")


