# -*- coding: utf-8 -*-
"""
IRIS - Web Tools
Ferramentas de busca na internet: search, news, reddit
"""

import requests

# ============================================================
# WEB SEARCH
# ============================================================

def fn_web_search(query, max_results=5):
    """Busca na web usando DuckDuckGo."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"- {r['title']}: {r['body'][:200]} ({r['href']})")
        
        return "\n".join(results) if results else f"Nenhum resultado: {query}"
    except Exception as e:
        return f"ERRO busca: {e}"


def fn_web_news(query, max_results=5):
    """Busca notícias usando DuckDuckGo."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append(
                    f"- [{r.get('source','')}] {r.get('title','')}: "
                    f"{r.get('body','')[:200]} ({r.get('url', r.get('href',''))})"
                )
        
        return "\n".join(results) if results else f"Nenhuma noticia: {query}"
    except Exception as e:
        return f"ERRO noticias: {e}"


# ============================================================
# REDDIT
# ============================================================

def fn_reddit(subreddit="technology", limit=8):
    """Busca posts populares em um subreddit."""
    aliases = {
        "tech": "technology",
        "ia": "artificial", 
        "brasil": "brasil",
        "news": "worldnews",
        "dev": "programming",
        "python": "Python",
        "startup": "startups",
        "finance": "finance"
    }
    
    sub = aliases.get(subreddit.lower(), subreddit)
    
    try:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
        resp = requests.get(url, headers={"User-Agent": "IRIS/1.0"}, timeout=15)
        
        if resp.status_code != 200:
            return f"Reddit HTTP {resp.status_code}"
        
        posts = []
        for c in resp.json().get("data", {}).get("children", []):
            p = c.get("data", {})
            posts.append(f"[{p.get('score',0)} pts] {p.get('title','')[:150]}")
        
        return "\n".join(posts) if posts else "Nenhum post."
    except Exception as e:
        return f"ERRO reddit: {e}"
