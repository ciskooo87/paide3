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

        query = (query or "").strip()
        if not query:
            return "❌ Query de busca vazia"

        safe_max_results = max(1, min(max_results, 10))

        try:
            results = []
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=safe_max_results):
                    results.append({
                        "title": result.get("title", "Sem título"),
                        "snippet": result.get("body", "")[:300],
                        "url": result.get("href", ""),
                    })

            if not results:
                return f"❌ Nenhum resultado encontrado para: {query}"

            output = f"🔍 **{len(results)} Resultados:** {query}\n\n"
            for i, result in enumerate(results, 1):
                output += f"**{i}. {result['title']}**\n"
                output += f"{result['snippet']}...\n"
                output += f"🔗 {result['url']}\n\n"

            return output

        except Exception as e:
            return f"❌ Erro: {str(e)}"