# -*- coding: utf-8 -*-
import os
from github import Github
from pathlib import Path

class GitHubTool:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.username = os.getenv("GITHUB_USERNAME", "ciskooo87")
        self.g = Github(self.token)
        
    def create_repo(self, repo_name, description=""):
        """Cria um novo repositório"""
        try:
            user = self.g.get_user()
            repo = user.create_repo(
                repo_name,
                description=description,
                private=False,
                auto_init=True
            )
            return f"✅ Repositório criado: {repo.html_url}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"
    
    def push_file(self, repo_name, file_path, commit_message="Update"):
        """Faz push de um arquivo para o repositório"""
        try:
            repo = self.g.get_repo(f"{self.username}/{repo_name}")
            
            # Lê o arquivo
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Nome do arquivo no repo
            file_name = Path(file_path).name
            
            # Verifica se arquivo já existe
            try:
                contents = repo.get_contents(file_name)
                repo.update_file(
                    contents.path,
                    commit_message,
                    content,
                    contents.sha
                )
                action = "Atualizado"
            except:
                repo.create_file(
                    file_name,
                    commit_message,
                    content
                )
                action = "Criado"
            
            return f"✅ {action}: {repo.html_url}/blob/main/{file_name}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"
    
    def push_directory(self, repo_name, dir_path, commit_message="Update project"):
        """Faz push de um diretório inteiro"""
        try:
            results = []
            for file_path in Path(dir_path).rglob('*'):
                if file_path.is_file() and not str(file_path).startswith('.'):
                    result = self.push_file(repo_name, str(file_path), commit_message)
                    results.append(result)
            return "\n".join(results)
        except Exception as e:
            return f"❌ Erro: {str(e)}"