# -*- coding: utf-8 -*-
"""
IRIS - GitHub Tools
Integração completa com GitHub API
"""

import requests
import base64

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import GITHUB_TOKEN, GITHUB_USER, GH_API, GH_HEADERS


# ============================================================
# GITHUB API REQUEST
# ============================================================

def gh_request(method, endpoint, data=None):
    """Faz requisição autenticada à API do GitHub."""
    if not GITHUB_TOKEN:
        return {"error": "GITHUB_TOKEN nao configurado no Render."}
    
    url = f"{GH_API}{endpoint}"
    
    try:
        if method == "GET":
            r = requests.get(url, headers=GH_HEADERS, timeout=15)
        elif method == "POST":
            r = requests.post(url, headers=GH_HEADERS, json=data, timeout=15)
        elif method == "PUT":
            r = requests.put(url, headers=GH_HEADERS, json=data, timeout=15)
        elif method == "PATCH":
            r = requests.patch(url, headers=GH_HEADERS, json=data, timeout=15)
        elif method == "DELETE":
            r = requests.delete(url, headers=GH_HEADERS, timeout=15)
        else:
            return {"error": f"Metodo desconhecido: {method}"}
        
        if r.status_code in (200, 201, 204):
            return r.json() if r.text else {"ok": True}
        
        return {"error": f"HTTP {r.status_code}: {r.text[:300]}"}
    
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# REPOSITORIES
# ============================================================

def fn_github_list_repos(user=None):
    """Lista repositórios do usuário."""
    u = user or GITHUB_USER
    if not u:
        return "GITHUB_USER nao configurado."
    
    result = gh_request("GET", f"/users/{u}/repos?sort=updated&per_page=15")
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    
    if not isinstance(result, list):
        return "Formato inesperado."
    
    repos = []
    for r in result[:15]:
        stars = r.get("stargazers_count", 0)
        lang = r.get("language", "N/A")
        updated = r.get("updated_at", "")[:10]
        private = " [PRIVADO]" if r.get("private") else ""
        repos.append(f"- {r['name']}{private} ({lang}, {stars} stars, atualizado {updated})")
    
    return "\n".join(repos) if repos else "Nenhum repositorio."


def fn_github_repo_info(repo):
    """Informações detalhadas de um repositório."""
    owner = GITHUB_USER
    if "/" in repo:
        parts = repo.split("/", 1)
        owner, repo = parts[0], parts[1]
    
    result = gh_request("GET", f"/repos/{owner}/{repo}")
    
    if "error" in result:
        return result["error"]
    
    info = (
        f"Repo: {result.get('full_name', repo)}\n"
        f"Descricao: {result.get('description', 'N/A')}\n"
        f"Linguagem: {result.get('language', 'N/A')}\n"
        f"Stars: {result.get('stargazers_count', 0)} | Forks: {result.get('forks_count', 0)}\n"
        f"Issues abertas: {result.get('open_issues_count', 0)}\n"
        f"Criado: {result.get('created_at', '')[:10]}\n"
        f"Atualizado: {result.get('updated_at', '')[:10]}\n"
        f"URL: {result.get('html_url', '')}"
    )
    
    return info


# ============================================================
# ISSUES
# ============================================================

def fn_github_list_issues(repo, state="open"):
    """Lista issues de um repositório."""
    owner = GITHUB_USER
    if "/" in repo:
        parts = repo.split("/", 1)
        owner, repo = parts[0], parts[1]
    
    result = gh_request("GET", f"/repos/{owner}/{repo}/issues?state={state}&per_page=10")
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    
    if not isinstance(result, list):
        return "Formato inesperado."
    
    issues = []
    for i in result[:10]:
        if i.get("pull_request"):
            continue  # Skip PRs
        
        labels = ", ".join(l["name"] for l in i.get("labels", []))
        issues.append(
            f"#{i['number']} [{i.get('state','')}] {i['title'][:80]}"
            + (f" ({labels})" if labels else "")
        )
    
    return "\n".join(issues) if issues else f"Nenhuma issue {state}."


def fn_github_create_issue(repo, title, body=""):
    """Cria nova issue."""
    owner = GITHUB_USER
    if "/" in repo:
        parts = repo.split("/", 1)
        owner, repo = parts[0], parts[1]
    
    result = gh_request("POST", f"/repos/{owner}/{repo}/issues", {"title": title, "body": body})
    
    if "error" in result:
        return result["error"]
    
    return f"Issue #{result.get('number', '?')} criada: {result.get('html_url', '')}"


# ============================================================
# FILES
# ============================================================

def fn_github_get_file(repo, path):
    """Lê arquivo ou lista diretório."""
    owner = GITHUB_USER
    if "/" in repo:
        parts = repo.split("/", 1)
        owner, repo = parts[0], parts[1]
    
    result = gh_request("GET", f"/repos/{owner}/{repo}/contents/{path}")
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    
    if isinstance(result, list):
        # Directory listing
        items = []
        for item in result[:30]:
            tp = item.get("type", "file")
            items.append(
                f"[{tp}] {item['name']}"
                + (f" ({item.get('size',0)}b)" if tp == "file" else "")
            )
        return "\n".join(items)
    
    # File content
    content = result.get("content", "")
    encoding = result.get("encoding", "")
    
    if encoding == "base64":
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
            return decoded[:4000]
        except:
            return "(erro ao decodificar)"
    
    return content[:4000]


def fn_github_create_or_update_file(repo, path, content, message="Update via IRIS"):
    """Cria ou atualiza arquivo no repositório."""
    owner = GITHUB_USER
    if "/" in repo:
        parts = repo.split("/", 1)
        owner, repo = parts[0], parts[1]
    
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    
    # Check if file exists (need SHA for update)
    existing = gh_request("GET", f"/repos/{owner}/{repo}/contents/{path}")
    sha = None
    if isinstance(existing, dict) and "sha" in existing:
        sha = existing["sha"]
    
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha
    
    result = gh_request("PUT", f"/repos/{owner}/{repo}/contents/{path}", payload)
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    
    action = "atualizado" if sha else "criado"
    url = result.get("content", {}).get("html_url", "")
    return f"Arquivo {action}: {path}\n{url}"


# ============================================================
# COMMITS
# ============================================================

def fn_github_list_commits(repo, n=10):
    """Lista commits recentes."""
    owner = GITHUB_USER
    if "/" in repo:
        parts = repo.split("/", 1)
        owner, repo = parts[0], parts[1]
    
    result = gh_request("GET", f"/repos/{owner}/{repo}/commits?per_page={n}")
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    
    if not isinstance(result, list):
        return "Formato inesperado."
    
    commits = []
    for c in result[:n]:
        sha = c.get("sha", "")[:7]
        msg = c.get("commit", {}).get("message", "")[:80]
        date = c.get("commit", {}).get("author", {}).get("date", "")[:10]
        author = c.get("commit", {}).get("author", {}).get("name", "")[:20]
        commits.append(f"[{sha}] {date} - {msg} ({author})")
    
    return "\n".join(commits) if commits else "Nenhum commit."


# ============================================================
# PULL REQUESTS
# ============================================================

def fn_github_list_prs(repo, state="open"):
    """Lista pull requests."""
    owner = GITHUB_USER
    if "/" in repo:
        parts = repo.split("/", 1)
        owner, repo = parts[0], parts[1]
    
    result = gh_request("GET", f"/repos/{owner}/{repo}/pulls?state={state}&per_page=10")
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    
    if not isinstance(result, list):
        return "Formato inesperado."
    
    prs = []
    for p in result[:10]:
        prs.append(
            f"#{p['number']} [{p.get('state','')}] {p['title'][:80]} "
            f"({p.get('user',{}).get('login','')})"
        )
    
    return "\n".join(prs) if prs else f"Nenhum PR {state}."


# ============================================================
# ACTIVITY
# ============================================================

def fn_github_activity():
    """Atividade recente no GitHub."""
    if not GITHUB_USER:
        return "GITHUB_USER nao configurado."
    
    result = gh_request("GET", f"/users/{GITHUB_USER}/events?per_page=15")
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    
    if not isinstance(result, list):
        return "Formato inesperado."
    
    events = []
    for e in result[:15]:
        tp = e.get("type", "")
        repo = e.get("repo", {}).get("name", "")
        date = e.get("created_at", "")[:16].replace("T", " ")
        
        if tp == "PushEvent":
            commits = e.get("payload", {}).get("commits", [])
            msg = commits[0].get("message", "")[:60] if commits else ""
            events.append(f"[{date}] Push -> {repo}: {msg}")
        elif tp == "CreateEvent":
            ref = e.get("payload", {}).get("ref_type", "")
            events.append(f"[{date}] Create {ref} -> {repo}")
        elif tp == "IssuesEvent":
            action = e.get("payload", {}).get("action", "")
            title = e.get("payload", {}).get("issue", {}).get("title", "")[:60]
            events.append(f"[{date}] Issue {action} -> {repo}: {title}")
        elif tp == "PullRequestEvent":
            action = e.get("payload", {}).get("action", "")
            title = e.get("payload", {}).get("pull_request", {}).get("title", "")[:60]
            events.append(f"[{date}] PR {action} -> {repo}: {title}")
        else:
            events.append(f"[{date}] {tp} -> {repo}")
    
    return "\n".join(events) if events else "Nenhuma atividade recente."
