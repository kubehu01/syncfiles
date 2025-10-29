"""
GitHub API 客户端
"""
import base64
from typing import List, Dict, Optional, TYPE_CHECKING
import time
import os
import logging

# 注意：避免与本地 github_api 包冲突，使用完整的导入
from github import Github

logger = logging.getLogger(__name__)


class GitHubAPI:
    """GitHub API 客户端"""
    
    def __init__(self, token: str, repo: str, branch: str = 'main', proxy_manager_ref=None):
        """
        初始化
        
        Args:
            token: GitHub Token
            repo: 仓库名称（格式：owner/repo）
            branch: 分支名称
            proxy_manager_ref: 代理管理器引用（ProxyManager 实例）
        """
        # 配置 GitHub 代理（动态检查，避免循环导入）
        if proxy_manager_ref and hasattr(proxy_manager_ref, 'is_proxy_enabled') and proxy_manager_ref.is_proxy_enabled():
            github_base_url = 'https://api.github.com'
            if proxy_manager_ref.should_use_proxy(github_base_url):
                proxy_conf = proxy_manager_ref.get_proxy_for_url(github_base_url)
                # GitHub PyGithub 库通过环境变量设置代理
                if proxy_conf and 'https' in proxy_conf:
                    os.environ['HTTPS_PROXY'] = proxy_conf['https']
                    logger.info(f"🔗 GitHub API 使用代理: {proxy_conf['https']}")
        
        self.github = Github(token)
        self.repo_name = repo  # 保存字符串形式的仓库名
        self.repo = self.github.get_repo(repo)  # Repository 对象
        self.branch = branch
        self.file_path = 'images.txt'
    
    def read_file(self) -> str:
        """
        读取 images.txt 文件内容
        
        Returns:
            文件内容
        """
        try:
            file = self.repo.get_contents(self.file_path, ref=self.branch)
            if file.encoding == 'base64':
                content = base64.b64decode(file.content).decode('utf-8')
            else:
                content = file.decoded_content.decode('utf-8')
            return content
        except Exception as e:
            # 文件不存在，返回空内容
            return ''
    
    def update_file(self, content: str, message: str = None) -> bool:
        """
        更新 images.txt 文件
        
        Args:
            content: 新内容
            message: 提交信息
            
        Returns:
            是否更新成功
        """
        try:
            if message is None:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                message = f"同步镜像 - {timestamp}"
            
            # 先尝试读取现有文件
            try:
                file = self.repo.get_contents(self.file_path, ref=self.branch)
                file_sha = file.sha
                file_exists = True
            except Exception:
                # 文件不存在
                file_sha = None
                file_exists = False
            
            if file_exists:
                # 文件存在，先置空再更新
                # 第一步：置空文件
                logger.info(f"清空文件: {self.file_path}")
                self.repo.update_file(
                    self.file_path,
                    "清空镜像列表",
                    "",
                    file_sha,
                    branch=self.branch
                )
                
                # 第二步：等待文件更新完成（避免并发问题）
                time.sleep(1)
                
                # 第三步：读取最新的 SHA 并更新内容
                logger.info(f"更新文件内容: {self.file_path}")
                updated_file = self.repo.get_contents(self.file_path, ref=self.branch)
                self.repo.update_file(
                    self.file_path,
                    message,
                    content,
                    updated_file.sha,
                    branch=self.branch
                )
            else:
                # 文件不存在，直接创建
                self.repo.create_file(
                    self.file_path,
                    message,
                    content,
                    branch=self.branch
                )
            
            return True
            
        except Exception as e:
            raise Exception(f"更新文件失败: {str(e)}")
    
    def append_images(self, images: List[str]) -> bool:
        """
        添加镜像到 images.txt（先清空再写入新内容）
        
        Args:
            images: 镜像列表
            
        Returns:
            是否更新成功
        """
        # 去重并排序
        unique_images = sorted(list(set(images)))
        
        # 生成新内容（只包含本次添加的镜像）
        new_content = '\n'.join(unique_images) + '\n' if unique_images else ''
        
        # 更新文件（update_file 会先清空再写入）
        return self.update_file(new_content, f"添加 {len(images)} 个镜像")
    
    def _parse_images(self, content: str) -> List[str]:
        """
        解析镜像列表
        
        Args:
            content: 文件内容
            
        Returns:
            镜像列表
        """
        images = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                images.append(line)
        return images
    
    def trigger_action(self) -> Dict[str, any]:
        """
        触发 GitHub Actions（通过更新文件）
        
        Returns:
            触发结果
        """
        # 通过更新空行来触发 GitHub Actions
        current_content = self.read_file()
        
        # 添加一个注释行
        new_content = current_content + '\n# Trigger sync ' + str(time.time())
        
        self.update_file(new_content.strip(), '触发同步任务')
        
        return {
            'success': True,
            'message': 'GitHub Actions 已触发',
            'timestamp': time.time()
        }
    
    def get_latest_workflow_run(self) -> Optional[Dict]:
        """
        获取最新的 workflow run
        
        Returns:
            最新的 workflow run 信息，如果没有则返回 None
        """
        try:
            # self.repo 已经是 Repository 对象，直接使用
            runs = self.repo.get_workflow_runs()
            
            if runs.totalCount > 0:
                latest_run = runs[0]
                return {
                    'id': latest_run.id,
                    'status': latest_run.status,
                    'conclusion': latest_run.conclusion,
                    'html_url': latest_run.html_url,
                    'created_at': latest_run.created_at,
                    'updated_at': latest_run.updated_at
                }
            
            return None
            
        except Exception as e:
            logger.error(f"获取 workflow run 失败: {str(e)}")
            return None


