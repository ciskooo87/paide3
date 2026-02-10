# -*- coding: utf-8 -*-
import os
from github import Github
from pathlib import Path
from typing import Optional

class GitHubTool:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.username = os.getenv("GITHUB_USERNAME", "ciskooo87")
        self.g: Optional[Github] = Github(self.token) if self.token else None

    def _ensure_client(self):
        if not self.g:
            raise RuntimeError("GITHUB_TOKEN não configurado")
        
    def create_repo(self, repo_name, description=""):
        """Cria um novo repositório"""
        try:
            self._ensure_client()
            user = self.g.get_user()
            repo = user.create_repo(repo_name, description=description, private=False, auto_init=True)
            return f"✅ Repo criado: {repo.html_url}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"
    
    def push_file(self, repo_name, file_path, commit_message="Update"):
        """Faz push de arquivo"""
        try:
            self._ensure_client()
            repo = self.g.get_repo(f"{self.username}/{repo_name}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            file_name = Path(file_path).name
            try:
                contents = repo.get_contents(file_name)
                repo.update_file(contents.path, commit_message, content, contents.sha)
                return f"✅ Atualizado: {repo.html_url}/blob/main/{file_name}"
            except Exception:
                repo.create_file(file_name, commit_message, content)
                return f"✅ Criado: {repo.html_url}/blob/main/{file_name}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"
