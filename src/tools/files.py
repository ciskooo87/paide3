# -*- coding: utf-8 -*-
"""
IRIS - File Management Tools
Upload, download e gerenciamento de arquivos do Telegram
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import WS_UPLOADS, WS_ROBERTO, WS_MARLEY


# ============================================================
# FILE LISTING
# ============================================================

def fn_list_received_files():
    """Lista arquivos recebidos via Telegram."""
    fs = [f for f in WS_UPLOADS.rglob("*") if f.is_file()]
    
    if not fs:
        return "Nenhum arquivo recebido."
    
    return "\n".join(f"- {f.name} ({f.stat().st_size:,}b)" for f in fs[:30])


# ============================================================
# FILE READING
# ============================================================

def fn_read_received_file(filename):
    """Lê arquivo recebido via Telegram."""
    p = WS_UPLOADS / filename
    
    if not p.exists():
        return f"Arquivo nao encontrado: {filename}"
    
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:4000]
    except:
        return f"Arquivo binario: {filename} ({p.stat().st_size:,}b). Use enviar_arquivo para enviar."


# ============================================================
# FILE PATH RESOLUTION
# ============================================================

def fn_get_file_path(filename):
    """Retorna caminho completo do arquivo (verifica múltiplos workspaces)."""
    for ws in (WS_UPLOADS, WS_ROBERTO, WS_MARLEY):
        p = ws / filename
        if p.exists():
            return str(p)
    return None
