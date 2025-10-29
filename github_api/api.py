"""
GitHub API 客户端
"""
import base64
from typing import List, Dict
import time
import os

# 注意：避免与本地 github_api 包冲突，使用完整的导入
from github import Github

# 代理配置
from utils.proxy import ProxyManager


class GitHubAPI:
    """GitHub API 客户端"""
    
    def __init__(self, token: str, repo: str, branch: str = 'main', proxy_manager_ref=None):
        """
        初始化
        
        Args:
            token: GitHub Token
            repo: 仓库名称（格式：owner/repo）
            branch: 分支名称
            proxy_manager_ref: 代理管理器引用
        """
        # 配置 GitHub 代理
        if proxy_manager_ref and proxy_manager_ref.is_proxy_enabled():
            github_base_url = 'https://api.github.com'
            if proxy_manager_ref.should_use_proxy(github_base_url):
                proxy_conf = proxy_manager_ref.get_proxy_for_url(github_base_url)
                # GitHub PyGithub 库通过环境变量设置代理
                if proxy_conf and 'https' in proxy_conf:
                    os.environ['HTTPS_PROXY'] = proxy_conf['https']
                    print(f"🔗 GitHub API 使用代理: {proxy_conf['https']}")
        
        self.github = Github(token)
        self.repo = self.github.get_repo(repo)
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
            
            try:
                # 尝试读取现有文件
                file = self.repo.get_contents(self.file_path, ref=self.branch)
                self.repo.update_file(
                    self.file_path,
                    message,
                    content,
                    file.sha,
                    branch=self.branch
                )
            except Exception:
                # 文件不存在，创建新文件
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
        追加镜像到 images.txt
        
        Args:
            images: 镜像列表
            
        Returns:
            是否更新成功
        """
        # 读取现有内容
        current_content = self.read_file()
        
        # 解析现有镜像
        existing_images = self._parse_images(current_content)
        
        # 添加新镜像
        all_images = list(set(existing_images + images))
        
        # 去重并排序
        all_images = sorted(list(set(all_images)))
        
        # 生成新内容
        new_content = '\n'.join(all_images) + '\n'
        
        # 更新文件
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

