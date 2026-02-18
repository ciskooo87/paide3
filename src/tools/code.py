# -*- coding: utf-8 -*-
"""
IRIS - Code Execution Tools
Execução de código Python e comandos Bash no workspace
"""

import subprocess
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import WS_ROBERTO, CODE_TIMEOUT


# ============================================================
# FILE OPERATIONS
# ============================================================

def fn_create_file(filename, content):
    """Cria arquivo no workspace."""
    try:
        p = WS_ROBERTO / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK: {filename} ({len(content)}b)"
    except Exception as e:
        return f"ERRO: {e}"


def fn_read_file(filename):
    """Lê arquivo do workspace."""
    try:
        p = WS_ROBERTO / filename
        if not p.exists():
            return f"Nao encontrado: {filename}"
        return p.read_text(encoding="utf-8")[:4000]
    except Exception as e:
        return f"ERRO: {e}"


def fn_list_workspace():
    """Lista arquivos no workspace."""
    fs = [
        f for f in WS_ROBERTO.rglob("*") 
        if f.is_file() and not f.name.startswith("_")
    ]
    
    if not fs:
        return "Vazio"
    
    return "\n".join(str(f.relative_to(WS_ROBERTO)) for f in fs[:30])


# ============================================================
# CODE EXECUTION
# ============================================================

def fn_run_python(code):
    """Executa código Python."""
    try:
        tmp = WS_ROBERTO / "_run.py"
        tmp.write_text(code, encoding="utf-8")
        
        r = subprocess.run(
            ["python3", str(tmp)],
            capture_output=True,
            text=True,
            timeout=CODE_TIMEOUT,
            cwd=str(WS_ROBERTO)
        )
        
        output = (r.stdout + "\n" + r.stderr).strip()
        return (output or "OK")[:3000]
    
    except subprocess.TimeoutExpired:
        return "ERRO: timeout"
    except Exception as e:
        return f"ERRO: {e}"


def fn_run_bash(command):
    """Executa comando bash/shell."""
    # Security checks
    if any(x in command for x in ["rm -rf /", "mkfs", ":(){ "]):
        return "Bloqueado"
    
    try:
        r = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=CODE_TIMEOUT,
            cwd=str(WS_ROBERTO)
        )
        
        output = (r.stdout + "\n" + r.stderr).strip()
        return (output or "OK")[:3000]
    
    except Exception as e:
        return f"ERRO: {e}"
