# -*- coding: utf-8 -*-
"""
IRIS - Image Generation
Geração de imagens com FLUX via Pollinations
"""

import requests
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import WS_MARLEY, IMAGE_TIMEOUT


# ============================================================
# IMAGE GENERATION
# ============================================================

def fn_generate_image(prompt):
    """Gera imagem usando FLUX via Pollinations (free, high quality)."""
    try:
        encoded = requests.utils.quote(prompt)
        seed = int(datetime.now().timestamp()) % 999999
        
        # Try with FLUX model first
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}&model=flux"
        print(f"[IMAGE] Generating: {url[:100]}...")
        
        resp = requests.get(url, timeout=IMAGE_TIMEOUT, stream=True)
        
        if resp.status_code == 200:
            data = b"".join(resp.iter_content(8192))
            if len(data) < 500:
                return None, "Imagem muito pequena"
            
            fp = WS_MARLEY / f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
            fp.write_bytes(data)
            return str(fp), url
        
        # Fallback without model param
        url2 = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}"
        resp2 = requests.get(url2, timeout=IMAGE_TIMEOUT, stream=True)
        
        if resp2.status_code == 200:
            data = b"".join(resp2.iter_content(8192))
            if len(data) >= 500:
                fp = WS_MARLEY / f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
                fp.write_bytes(data)
                return str(fp), url2
        
        return None, f"HTTP {resp.status_code}/{resp2.status_code}"
    
    except Exception as e:
        return None, f"ERRO: {e}"
