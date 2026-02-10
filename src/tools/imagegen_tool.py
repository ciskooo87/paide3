# -*- coding: utf-8 -*-
import os
import replicate
import requests
from io import BytesIO

class ImageGeneratorTool:
    def __init__(self):
        self.api_token = os.getenv("REPLICATE_API_TOKEN")
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token
    
    def generate(self, prompt):
        """Gera imagem com FLUX via Replicate"""
        try:
            if not self.api_token:
                return None, "❌ REPLICATE_API_TOKEN não configurado"
            
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={"prompt": prompt}
            )
            
            # output é uma lista com URL da imagem
            if output and len(output) > 0:
                image_url = output[0]
                
                # Baixa a imagem
                response = requests.get(image_url, timeout=30)
                if response.status_code == 200:
                    return BytesIO(response.content), image_url
                    
            return None, "❌ Erro ao gerar imagem"
        except Exception as e:
            return None, f"❌ Erro: {str(e)}"