# -*- coding: utf-8 -*-
"""
IRIS - Configurações Centralizadas
Todas as variáveis de ambiente, constantes e configurações do bot
"""

import os
from pathlib import Path
from datetime import timezone, timedelta

# ============================================================
# API KEYS & CREDENTIALS
# ============================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Email
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
CORP_EMAIL = os.getenv("CORP_EMAIL", "")
CORP_PASSWORD = os.getenv("CORP_PASSWORD", "")
CORP_IMAP_SERVER = os.getenv("CORP_IMAP_SERVER", "")

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_USER = os.getenv("GITHUB_USER", "")

# ============================================================
# MODEL CONFIG
# ============================================================

DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ============================================================
# TIMEZONE & PATHS
# ============================================================

BRT = timezone(timedelta(hours=-3))

BASE_DIR = Path(__file__).resolve().parent.parent
WS_ROBERTO = BASE_DIR / "workspace" / "roberto"
WS_CURIOSO = BASE_DIR / "workspace" / "curioso"
WS_MARLEY = BASE_DIR / "workspace" / "marley"
WS_UPLOADS = BASE_DIR / "workspace" / "uploads"
DATA_DIR = BASE_DIR / "data"

# Criar diretórios se não existirem
for d in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY, WS_UPLOADS, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# GITHUB API
# ============================================================

GH_API = "https://api.github.com"
GH_HEADERS = {}
if GITHUB_TOKEN:
    GH_HEADERS = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "IRIS-Agent/1.0",
    }

# ============================================================
# CONVERSATION SETTINGS
# ============================================================

MAX_HISTORY = 30
MAX_LLM_ROUNDS = 8
MAX_TOKENS = 4000
TEMPERATURE = 0.3

# ============================================================
# FILE UPLOAD LIMITS
# ============================================================

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# ============================================================
# TIMEOUTS
# ============================================================

HTTP_TIMEOUT = 15
IMAGE_TIMEOUT = 120
CODE_TIMEOUT = 30
