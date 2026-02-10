# -*- coding: utf-8 -*-
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup

class WebSearchTool:
    def search(self, query, max_results=5):
        """Busca na web com DuckDuckGo"""
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        'title': r['title'],
                        'snippet': r['body'][:200],
                        'url': r['href']
                    })
            
            # Formata resposta
            output = f"🔍 Resultados para: {query}\n\n"
            for i, r in enumerate(results, 1):
                output += f"{i}. **{r['title']}**\n"
                output += f"   {r['snippet']}...\n"
                output += f"   🔗 {r['url']}\n\n"
            
            return output
        except Exception as e:
            return f"❌ Erro na busca: {str(e)}"
    
    def scrape_url(self, url):
        """Extrai texto de uma URL"""
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove scripts e styles
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:3000]  # Limita tamanho
        except Exception as e:
            return f"❌ Erro ao extrair: {str(e)}"