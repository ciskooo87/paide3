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
        """Gera imagem com FLUX"""
        if not self.api_token:
            return None, "❌ Token não configurado"

        prompt = (prompt or "").strip()
        if not prompt:
            return None, "❌ Prompt vazio"

        try:
            output = replicate.run("black-forest-labs/flux-schnell", input={"prompt": prompt})
            if output and len(output) > 0:
                image_url = output[0]
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()
                return BytesIO(response.content), image_url

            return None, "❌ Erro ao gerar"
        except Exception as e:
            return None, f"❌ Erro: {str(e)}"