# -*- coding: utf-8 -*-
try:
    from duckduckgo_search import DDGS
except ImportError:
    try:
        from ddgs import DDGS
    except ImportError:
        DDGS = None

class WebSearchTool:
    def search(self, query, max_results=5):
        """Busca na web"""
        if DDGS is None:
            return f"❌ Módulo de busca não disponível. Query: {query}"
        
        try:
            results = []
            ddgs = DDGS()
            
            search_results = ddgs.text(query, max_results=max_results)
            
            for r in search_results:
                results.append({
                    'title': r.get('title', 'Sem título'),
                    'snippet': r.get('body', '')[:300],
                    'url': r.get('href', '')
                })
            
            if not results:
                return f"❌ Nenhum resultado encontrado para: {query}"
            
            output = f"🔍 **{len(results)} Resultados:** {query}\n\n"
            for i, r in enumerate(results, 1):
                output += f"**{i}. {r['title']}**\n"
                output += f"{r['snippet']}...\n"
                output += f"🔗 {r['url']}\n\n"
            
            return output
            
        except Exception as e:
            return f"❌ Erro: {str(e)}"