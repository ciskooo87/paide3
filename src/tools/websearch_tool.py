# -*- coding: utf-8 -*-
from duckduckgo_search import DDGS

class WebSearchTool:
    def search(self, query, max_results=5):
        """Busca na web com DuckDuckGo"""
        try:
            results = []
            ddgs = DDGS()
            
            # Usa text() ao invés de context manager
            search_results = ddgs.text(query, max_results=max_results)
            
            for r in search_results:
                results.append({
                    'title': r.get('title', 'Sem título'),
                    'snippet': r.get('body', '')[:300],
                    'url': r.get('href', '')
                })
            
            if not results:
                return f"❌ Nenhum resultado encontrado para: {query}"
            
            # Formata resposta
            output = f"🔍 **{len(results)} Resultados para:** {query}\n\n"
            for i, r in enumerate(results, 1):
                output += f"**{i}. {r['title']}**\n"
                output += f"{r['snippet']}...\n"
                output += f"🔗 {r['url']}\n\n"
            
            return output
            
        except Exception as e:
            return f"❌ Erro na busca: {str(e)}\nQuery: {query}"
    
    def scrape_url(self, url):
        """Extrai texto de uma URL"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove scripts e styles
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            text = ' '.join(line for line in lines if line)
            
            return text[:3000]  # Limita tamanho
        except Exception as e:
            return f"❌ Erro ao extrair: {str(e)}"