"""
文件锁管理
"""
import os
import time
import json
from pathlib import Path


class TaskLock:
    """任务锁管理"""
    
    def __init__(self, lock_file: str = '.task_lock'):
        """
        初始化
        
        Args:
            lock_file: 锁文件路径
        """
        self.lock_file = Path(lock_file)
        self.lock_timeout = 300  # 5 分钟超时
    
    def acquire(self) -> bool:
        """
        获取锁
        
        Returns:
            是否成功获取锁
        """
        try:
            # 检查是否已有锁
            if self.lock_file.exists():
                # 检查锁是否超时
                try:
                    lock_data = json.loads(self.lock_file.read_text())
                    lock_time = lock_data.get('timestamp', 0)
                    
                    if time.time() - lock_time < self.lock_timeout:
                        return False
                    else:
                        # 锁已超时，删除
                        self.lock_file.unlink()
                except (json.JSONDecodeError, ValueError, OSError):
                    # 锁文件损坏或读取失败，删除并重新创建
                    try:
                        self.lock_file.unlink()
                    except OSError:
                        pass
            
            # 创建新锁
            lock_data = {
                'timestamp': time.time(),
                'pid': os.getpid()
            }
            self.lock_file.write_text(json.dumps(lock_data))
            return True
        except Exception:
            # 任何异常都返回 False，表示获取锁失败
            return False
    
    def release(self) -> bool:
        """
        释放锁
        
        Returns:
            是否成功释放锁
        """
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
                return True
            return False
        except OSError:
            # 文件删除失败，但锁已失效或不存在，视为成功
            return True
    
    def is_locked(self) -> bool:
        """
        检查是否已锁定
        
        Returns:
            是否已锁定
        """
        if not self.lock_file.exists():
            return False
        
        try:
            lock_data = json.loads(self.lock_file.read_text())
            lock_time = lock_data.get('timestamp', 0)
            
            # 检查是否超时
            if time.time() - lock_time >= self.lock_timeout:
                self.release()
                return False
            
            return True
        except (json.JSONDecodeError, ValueError, OSError):
            # 锁文件损坏，视为未锁定
            try:
                self.lock_file.unlink()
            except OSError:
                pass
            return False

