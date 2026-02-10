# -*- coding: utf-8 -*-
from duckduckgo_search import DDGS

class WebSearchTool:
    def search(self, query, max_results=5):
        """Busca na web"""
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({'title': r['title'], 'snippet': r['body'][:200], 'url': r['href']})
            output = f"🔍 Resultados: {query}\n\n"
            for i, r in enumerate(results, 1):
                output += f"{i}. {r['title']}\n   {r['snippet']}...\n   {r['url']}\n\n"
            return output
        except Exception as e:
            return f"❌ Erro: {str(e)}"