# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v9.0 - IRIS
Agente mestre com linguagem natural + modo noturno de reflexao.
Sem necessidade de comandos com barra.
LLM: DeepSeek V3 via OpenAI-compatible API
Deploy: Render.com Background Worker
"""

import os
import re
import json
import subprocess
import logging
import warnings
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta, timezone, time as dt_time
from io import BytesIO
from pathlib import Path

warnings.filterwarnings("ignore")
logging.getLogger("httpx").setLevel(logging.WARNING)

import requests as http_requests
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, CallbackContext, filters,
)

# ============================================================
# CONFIG
# ============================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
CORP_EMAIL = os.getenv("CORP_EMAIL", "")
CORP_PASSWORD = os.getenv("CORP_PASSWORD", "")
CORP_IMAP_SERVER = os.getenv("CORP_IMAP_SERVER", "")

BRT = timezone(timedelta(hours=-3))
BASE_DIR = Path(__file__).resolve().parent.parent
WS_ROBERTO = BASE_DIR / "workspace" / "roberto"
WS_CURIOSO = BASE_DIR / "workspace" / "curioso"
WS_MARLEY = BASE_DIR / "workspace" / "marley"
DATA_DIR = BASE_DIR / "data"

for d in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


# ============================================================
# STORAGE
# ============================================================

def load_data(name):
    f = DATA_DIR / f"{name}.json"
    if f.exists():
        try: return json.loads(f.read_text(encoding="utf-8"))
        except: return {}
    return {}

def save_data(name, data):
    f = DATA_DIR / f"{name}.json"
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def today_str(): return datetime.now(BRT).strftime("%Y-%m-%d")
def now_str(): return datetime.now(BRT).strftime("%Y-%m-%d %H:%M")
def week_key():
    d = datetime.now(BRT)
    return (d - timedelta(days=d.weekday())).strftime("%Y-W%W")


# ============================================================
# CONVERSATION HISTORY
# ============================================================

MAX_HISTORY = 30

def get_history():
    data = load_data("historico")
    return data.get("mensagens", [])

def add_to_history(role, content):
    data = load_data("historico")
    if "mensagens" not in data:
        data["mensagens"] = []
    data["mensagens"].append({
        "role": role,
        "content": content[:1000],
        "time": now_str(),
    })
    # Keep last N
    data["mensagens"] = data["mensagens"][-MAX_HISTORY:]
    save_data("historico", data)


# ============================================================
# LLM
# ============================================================

def chat_simple(system_prompt, user_message, max_tokens=4000):
    try:
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], max_tokens=max_tokens, temperature=0.3)
        return r.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERRO] {e}"


# ============================================================
# CAPABILITY FUNCTIONS (all bot features as callable functions)
# ============================================================

# --- WEB SEARCH ---

def fn_web_search(query, max_results=5):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"- {r['title']}: {r['body'][:200]} ({r['href']})")
        return "\n".join(results) if results else f"Nenhum resultado para: {query}"
    except Exception as e:
        return f"ERRO busca: {e}"


def fn_web_news(query, max_results=5):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append(
                    f"- [{r.get('source','')}] {r.get('title','')}: "
                    f"{r.get('body','')[:200]} ({r.get('url', r.get('href',''))})")
        return "\n".join(results) if results else f"Nenhuma noticia: {query}"
    except Exception as e:
        return f"ERRO noticias: {e}"


# --- EMAIL ---

def decode_mime_header(raw):
    if not raw: return ""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try: decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except: decoded.append(part.decode("utf-8", errors="replace"))
        else: decoded.append(str(part))
    return " ".join(decoded)

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    break
                except: pass
            elif ct == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    body = re.sub(r'<[^>]+>', ' ', html); body = re.sub(r'\s+', ' ', body).strip()
                except: pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        except: body = str(msg.get_payload())
    return body[:1500]


def fn_read_emails(conta="gmail", n=5):
    if conta == "gmail":
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            return "Gmail nao configurado. Configure GMAIL_EMAIL e GMAIL_APP_PASSWORD no Render."
        addr, pwd, srv = GMAIL_EMAIL, GMAIL_APP_PASSWORD, "imap.gmail.com"
    else:
        if not CORP_EMAIL or not CORP_PASSWORD:
            return "Email corporativo nao configurado."
        addr, pwd, srv = CORP_EMAIL, CORP_PASSWORD, CORP_IMAP_SERVER or "imap.gmail.com"
    try:
        mail = imaplib.IMAP4_SSL(srv)
        mail.login(addr, pwd)
        mail.select("INBOX", readonly=True)
        _, data = mail.search(None, "ALL")
        ids = data[0].split()
        if not ids: mail.logout(); return "Caixa vazia."
        results = []
        for eid in list(reversed(ids[-n:])):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])
            results.append(
                f"De: {decode_mime_header(msg.get('From',''))[:80]}\n"
                f"Assunto: {decode_mime_header(msg.get('Subject',''))[:120]}\n"
                f"Data: {msg.get('Date','')[:25]}\n"
                f"Corpo: {get_email_body(msg)[:300]}\n")
        mail.logout()
        return "\n---\n".join(results) if results else "Nenhum email."
    except Exception as e:
        return f"ERRO email: {e}"


# --- REDDIT ---

def fn_reddit(subreddit="technology", limit=8):
    aliases = {"tech": "technology", "ia": "artificial", "brasil": "brasil",
        "news": "worldnews", "dev": "programming", "python": "Python",
        "startup": "startups", "finance": "finance"}
    sub = aliases.get(subreddit.lower(), subreddit)
    try:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
        resp = http_requests.get(url, headers={"User-Agent": "IRONCORE/1.0"}, timeout=15)
        if resp.status_code != 200: return f"Reddit HTTP {resp.status_code}"
        posts = []
        for c in resp.json().get("data", {}).get("children", []):
            p = c.get("data", {})
            posts.append(f"[{p.get('score',0)} pts] {p.get('title','')[:150]}")
        return "\n".join(posts) if posts else "Nenhum post."
    except Exception as e:
        return f"ERRO reddit: {e}"


# --- IMAGE ---

def fn_generate_image(prompt):
    try:
        encoded = http_requests.utils.quote(prompt)
        seed = int(datetime.now().timestamp()) % 999999
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}"
        resp = http_requests.get(url, timeout=120, stream=True)
        if resp.status_code == 200:
            data = b"".join(resp.iter_content(8192))
            if len(data) < 500: return None, f"Imagem muito pequena"
            fp = WS_MARLEY / f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
            fp.write_bytes(data)
            return str(fp), url
        url2 = f"https://pollinations.ai/p/{encoded}"
        resp2 = http_requests.get(url2, timeout=120, stream=True)
        if resp2.status_code == 200:
            data = b"".join(resp2.iter_content(8192))
            if len(data) >= 500:
                fp = WS_MARLEY / f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
                fp.write_bytes(data)
                return str(fp), url2
        return None, f"HTTP {resp.status_code}"
    except Exception as e:
        return None, f"ERRO: {e}"


# --- ROBERTO (code) ---

def fn_create_file(filename, content):
    try:
        p = WS_ROBERTO / filename; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8"); return f"OK: {filename} ({len(content)}b)"
    except Exception as e: return f"ERRO: {e}"

def fn_run_python(code):
    try:
        tmp = WS_ROBERTO / "_run.py"; tmp.write_text(code, encoding="utf-8")
        r = subprocess.run(["python3", str(tmp)], capture_output=True, text=True,
            timeout=30, cwd=str(WS_ROBERTO))
        return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
    except subprocess.TimeoutExpired: return "ERRO: timeout"
    except Exception as e: return f"ERRO: {e}"

def fn_run_bash(command):
    if any(x in command for x in ["rm -rf /", "mkfs", ":(){ "]): return "Bloqueado"
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=str(WS_ROBERTO))
        return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
    except Exception as e: return f"ERRO: {e}"

def fn_read_file(filename):
    try:
        p = WS_ROBERTO / filename
        if not p.exists(): return f"Nao encontrado: {filename}"
        return p.read_text(encoding="utf-8")[:4000]
    except Exception as e: return f"ERRO: {e}"

def fn_list_workspace():
    fs = [f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")]
    return "\n".join(str(f.relative_to(WS_ROBERTO)) for f in fs[:30]) if fs else "Vazio"


# --- TASKS ---

def fn_add_task(texto):
    data = load_data("tarefas")
    if "items" not in data: data["items"] = []; data["next_id"] = 1
    tid = data["next_id"]
    data["items"].append({"id": tid, "texto": texto, "criada": now_str(), "feita": False, "feita_em": None})
    data["next_id"] = tid + 1; save_data("tarefas", data)
    return f"Tarefa #{tid}: {texto}"

def fn_list_tasks():
    data = load_data("tarefas")
    pend = [t for t in data.get("items", []) if not t["feita"]]
    feitas = [t for t in data.get("items", []) if t["feita"] and (t.get("feita_em") or "").startswith(today_str())]
    msg = ""
    if pend: msg += "PENDENTES:\n" + "\n".join(f"  #{t['id']} {t['texto']}" for t in pend)
    if feitas: msg += f"\nHOJE ({len(feitas)}):\n" + "\n".join(f"  #{t['id']} {t['texto']}" for t in feitas)
    return msg or "Nenhuma tarefa."

def fn_complete_task(task_id):
    data = load_data("tarefas")
    for t in data.get("items", []):
        if t["id"] == task_id and not t["feita"]:
            t["feita"] = True; t["feita_em"] = now_str(); save_data("tarefas", data)
            return f"#{task_id} concluida: {t['texto']}"
    return f"#{task_id} nao encontrada."


# --- GOALS ---

def fn_add_goal(texto):
    data = load_data("metas"); wk = week_key()
    if wk not in data: data[wk] = []
    data[wk].append({"texto": texto, "criada": now_str(), "concluida": False})
    save_data("metas", data)
    return f"Meta semanal: {texto}"

def fn_list_goals():
    data = load_data("metas"); wk = week_key(); metas = data.get(wk, [])
    if not metas: return "Sem metas esta semana."
    return "\n".join(f"  {i}. [{'OK' if m['concluida'] else '...'}] {m['texto']}"
        for i, m in enumerate(metas, 1))


# --- JOURNAL ---

def fn_add_journal(texto):
    data = load_data("diario"); hoje = today_str()
    if hoje not in data: data[hoje] = []
    data[hoje].append({"hora": datetime.now(BRT).strftime("%H:%M"), "texto": texto})
    save_data("diario", data)
    return f"Diario registrado ({len(data[hoje])}a entrada)"

def fn_view_journal():
    data = load_data("diario"); hoje = today_str()
    entries = data.get(hoje, [])
    if not entries: return "Diario vazio hoje."
    return "\n".join(f"[{e['hora']}] {e['texto']}" for e in entries)


# --- EXERCISE ---

def fn_log_exercise(tipo):
    data = load_data("treinos"); hoje = today_str()
    if hoje not in data: data[hoje] = []
    data[hoje].append({"hora": datetime.now(BRT).strftime("%H:%M"), "tipo": tipo})
    save_data("treinos", data)
    wk = sum(len(data.get((datetime.now(BRT)-timedelta(days=i)).strftime("%Y-%m-%d"), []))
        for i in range(7))
    return f"Treino: {tipo}. Semana: {wk} sessao(es)"


# --- MOOD ---

def fn_log_mood(nivel, nota=""):
    data = load_data("humor"); hoje = today_str()
    if hoje not in data: data[hoje] = []
    data[hoje].append({"hora": datetime.now(BRT).strftime("%H:%M"), "nivel": nivel, "nota": nota})
    save_data("humor", data)
    labels = ["", "pessimo", "ruim", "neutro", "bom", "otimo"]
    return f"Humor: {nivel}/5 ({labels[nivel]}) {nota}"


# --- DASHBOARD ---

def fn_dashboard():
    hoje = today_str()
    diario = load_data("diario").get(hoje, [])
    tarefas = load_data("tarefas")
    pend = [t for t in tarefas.get("items", []) if not t["feita"]]
    feitas = [t for t in tarefas.get("items", []) if t["feita"] and (t.get("feita_em") or "").startswith(hoje)]
    pomos = load_data("pomodoros").get(hoje, [])
    treinos = load_data("treinos").get(hoje, [])
    humor = load_data("humor").get(hoje, [])
    metas = load_data("metas").get(week_key(), [])
    msg = f"DASHBOARD {hoje}\n"
    msg += f"Diario: {len(diario)} entradas\n"
    msg += f"Tarefas: {len(feitas)} feitas / {len(pend)} pendentes\n"
    if pend: msg += "".join(f"  #{t['id']} {t['texto'][:40]}\n" for t in pend[:5])
    msg += f"Pomodoros: {len(pomos)}\n"
    msg += f"Treino: {len(treinos)}\n"
    if humor: msg += f"Humor: {humor[-1]['nivel']}/5 {humor[-1].get('nota','')}\n"
    if metas:
        ok = sum(1 for m in metas if m["concluida"])
        msg += f"Metas: {ok}/{len(metas)}\n"
    return msg


# --- BRIEFING ---

def fn_briefing():
    parts = []
    # News
    news = ""
    for q in ["Brasil economia hoje", "AI technology news 2026", "world news today"]:
        news += fn_web_news(q, 3) + "\n"
    # Reddit
    reddit = fn_reddit("technology", 5)
    # Email
    email_txt = fn_read_emails("gmail", 5) if GMAIL_EMAIL else "(nao configurado)"
    # Tasks
    tasks = fn_list_tasks()
    # Goals
    goals = fn_list_goals()
    # Night thoughts
    pensamentos = load_data("pensamentos_noturnos")
    ultimo = pensamentos.get("ultimo", "")
    return (
        f"NOTICIAS:\n{news}\n\n"
        f"REDDIT:\n{reddit}\n\n"
        f"EMAILS:\n{email_txt}\n\n"
        f"TAREFAS:\n{tasks}\n\n"
        f"METAS:\n{goals}\n\n"
        f"REFLEXAO NOTURNA:\n{ultimo or '(nenhuma ainda)'}"
    )


# --- REVIEW ---

def fn_weekly_review():
    days = [(datetime.now(BRT)-timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    diario = load_data("diario"); tarefas = load_data("tarefas")
    pomos = load_data("pomodoros"); treinos = load_data("treinos")
    humor = load_data("humor"); metas_data = load_data("metas")
    ctx = ""
    for d in days:
        for e in diario.get(d, []): ctx += f"DIARIO {d}: {e['texto'][:150]}\n"
    for t in tarefas.get("items", []):
        if t["feita"] and (t.get("feita_em") or "")[:10] in days:
            ctx += f"TAREFA OK: {t['texto']}\n"
    ctx += f"PENDENTES: {len([t for t in tarefas.get('items', []) if not t['feita']])}\n"
    ctx += f"POMODOROS: {sum(len(pomos.get(d, [])) for d in days)}\n"
    for d in days:
        for t in treinos.get(d, []): ctx += f"TREINO {d}: {t['tipo']}\n"
        for h in humor.get(d, []): ctx += f"HUMOR {d}: {h['nivel']}/5 {h.get('nota','')}\n"
    for m in metas_data.get(week_key(), []):
        ctx += f"META [{'OK' if m['concluida'] else '...'}]: {m['texto']}\n"
    return ctx


# ============================================================
# IRIS - MASTER AGENT TOOLS DEFINITION
# ============================================================

IRIS_TOOLS = [
    {"type": "function", "function": {
        "name": "pesquisar_web",
        "description": "Pesquisa na internet. Use para qualquer pergunta factual, noticias, informacoes.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Termos de busca"}
        }, "required": ["query"]}}},

    {"type": "function", "function": {
        "name": "buscar_noticias",
        "description": "Busca noticias recentes sobre um tema.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Tema das noticias"},
            "n": {"type": "integer", "description": "Quantidade (default 5)"}
        }, "required": ["query"]}}},

    {"type": "function", "function": {
        "name": "ler_emails",
        "description": "Le emails recentes. Conta: gmail ou corp.",
        "parameters": {"type": "object", "properties": {
            "conta": {"type": "string", "enum": ["gmail", "corp"], "description": "Conta de email"},
            "n": {"type": "integer", "description": "Quantidade (default 5)"}
        }, "required": ["conta"]}}},

    {"type": "function", "function": {
        "name": "ver_reddit",
        "description": "Mostra posts populares de um subreddit.",
        "parameters": {"type": "object", "properties": {
            "subreddit": {"type": "string", "description": "Nome do subreddit (ex: technology, brasil, artificial)"}
        }, "required": ["subreddit"]}}},

    {"type": "function", "function": {
        "name": "gerar_imagem",
        "description": "Gera imagem com IA a partir de descricao. Crie prompt detalhado em ingles.",
        "parameters": {"type": "object", "properties": {
            "prompt": {"type": "string", "description": "Prompt detalhado em INGLES para gerar imagem"}
        }, "required": ["prompt"]}}},

    {"type": "function", "function": {
        "name": "criar_arquivo",
        "description": "Cria arquivo de codigo no workspace.",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string"}, "content": {"type": "string"}
        }, "required": ["filename", "content"]}}},

    {"type": "function", "function": {
        "name": "executar_codigo",
        "description": "Executa codigo Python e retorna resultado.",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Codigo Python"}
        }, "required": ["code"]}}},

    {"type": "function", "function": {
        "name": "executar_comando",
        "description": "Executa comando shell/bash.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}
        }, "required": ["command"]}}},

    {"type": "function", "function": {
        "name": "ler_arquivo",
        "description": "Le conteudo de arquivo do workspace.",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string"}
        }, "required": ["filename"]}}},

    {"type": "function", "function": {
        "name": "listar_arquivos",
        "description": "Lista arquivos no workspace de codigo.",
        "parameters": {"type": "object", "properties": {}}}},

    {"type": "function", "function": {
        "name": "adicionar_tarefa",
        "description": "Adiciona nova tarefa/to-do.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string", "description": "Descricao da tarefa"}
        }, "required": ["texto"]}}},

    {"type": "function", "function": {
        "name": "ver_tarefas",
        "description": "Lista tarefas pendentes e concluidas hoje.",
        "parameters": {"type": "object", "properties": {}}}},

    {"type": "function", "function": {
        "name": "completar_tarefa",
        "description": "Marca tarefa como concluida pelo numero.",
        "parameters": {"type": "object", "properties": {
            "task_id": {"type": "integer", "description": "Numero da tarefa"}
        }, "required": ["task_id"]}}},

    {"type": "function", "function": {
        "name": "adicionar_meta",
        "description": "Adiciona meta semanal.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string"}
        }, "required": ["texto"]}}},

    {"type": "function", "function": {
        "name": "ver_metas",
        "description": "Lista metas da semana atual.",
        "parameters": {"type": "object", "properties": {}}}},

    {"type": "function", "function": {
        "name": "registrar_diario",
        "description": "Adiciona entrada no diario/journal.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string"}
        }, "required": ["texto"]}}},

    {"type": "function", "function": {
        "name": "ver_diario",
        "description": "Mostra entradas do diario de hoje.",
        "parameters": {"type": "object", "properties": {}}}},

    {"type": "function", "function": {
        "name": "registrar_treino",
        "description": "Registra exercicio/treino realizado.",
        "parameters": {"type": "object", "properties": {
            "tipo": {"type": "string", "description": "Tipo de exercicio (ex: musculacao, corrida, yoga)"}
        }, "required": ["tipo"]}}},

    {"type": "function", "function": {
        "name": "registrar_humor",
        "description": "Registra nivel de humor/energia de 1 (pessimo) a 5 (otimo).",
        "parameters": {"type": "object", "properties": {
            "nivel": {"type": "integer", "description": "1-5"},
            "nota": {"type": "string", "description": "Observacao opcional"}
        }, "required": ["nivel"]}}},

    {"type": "function", "function": {
        "name": "ver_dashboard",
        "description": "Mostra dashboard completo do dia (tarefas, humor, treinos, etc).",
        "parameters": {"type": "object", "properties": {}}}},

    {"type": "function", "function": {
        "name": "briefing_matinal",
        "description": "Gera briefing matinal completo (noticias, emails, reddit, tarefas, metas).",
        "parameters": {"type": "object", "properties": {}}}},

    {"type": "function", "function": {
        "name": "review_semanal",
        "description": "Gera review/analise da semana com nota e sugestoes.",
        "parameters": {"type": "object", "properties": {}}}},
]


# ============================================================
# IRIS TOOL EXECUTOR
# ============================================================

def iris_execute_tool(fn_name, fn_args):
    """Execute any IRIS tool and return result."""
    print(f"[IRIS] Tool: {fn_name}({json.dumps(fn_args, ensure_ascii=False)[:100]})")

    if fn_name == "pesquisar_web":
        return fn_web_search(fn_args.get("query", ""))
    elif fn_name == "buscar_noticias":
        return fn_web_news(fn_args.get("query", ""), fn_args.get("n", 5))
    elif fn_name == "ler_emails":
        return fn_read_emails(fn_args.get("conta", "gmail"), fn_args.get("n", 5))
    elif fn_name == "ver_reddit":
        return fn_reddit(fn_args.get("subreddit", "technology"))
    elif fn_name == "gerar_imagem":
        path, url = fn_generate_image(fn_args.get("prompt", ""))
        return f"IMAGE_PATH={path} IMAGE_URL={url}" if path else f"ERRO: {url}"
    elif fn_name == "criar_arquivo":
        return fn_create_file(fn_args.get("filename", "out.py"), fn_args.get("content", ""))
    elif fn_name == "executar_codigo":
        return fn_run_python(fn_args.get("code", ""))
    elif fn_name == "executar_comando":
        return fn_run_bash(fn_args.get("command", ""))
    elif fn_name == "ler_arquivo":
        return fn_read_file(fn_args.get("filename", ""))
    elif fn_name == "listar_arquivos":
        return fn_list_workspace()
    elif fn_name == "adicionar_tarefa":
        return fn_add_task(fn_args.get("texto", ""))
    elif fn_name == "ver_tarefas":
        return fn_list_tasks()
    elif fn_name == "completar_tarefa":
        return fn_complete_task(fn_args.get("task_id", 0))
    elif fn_name == "adicionar_meta":
        return fn_add_goal(fn_args.get("texto", ""))
    elif fn_name == "ver_metas":
        return fn_list_goals()
    elif fn_name == "registrar_diario":
        return fn_add_journal(fn_args.get("texto", ""))
    elif fn_name == "ver_diario":
        return fn_view_journal()
    elif fn_name == "registrar_treino":
        return fn_log_exercise(fn_args.get("tipo", ""))
    elif fn_name == "registrar_humor":
        return fn_log_mood(fn_args.get("nivel", 3), fn_args.get("nota", ""))
    elif fn_name == "ver_dashboard":
        return fn_dashboard()
    elif fn_name == "briefing_matinal":
        return fn_briefing()
    elif fn_name == "review_semanal":
        return fn_weekly_review()
    return f"Funcao desconhecida: {fn_name}"


# ============================================================
# IRIS SYSTEM PROMPT
# ============================================================

IRIS_SYSTEM = (
    "Voce e IRIS, assistente pessoal inteligente do Paulo. "
    "Voce coordena TUDO: pesquisas, codigo, imagens, tarefas, emails, noticias, saude. "
    "Voce fala de forma natural, direta e eficiente em portugues. "
    "Voce NUNCA pede para o usuario usar comandos com barra. "
    "Voce age proativamente - se alguem diz 'bom dia', voce oferece o briefing. "
    "Se alguem menciona uma tarefa, voce registra automaticamente. "
    "Se alguem pergunta algo factual, voce pesquisa na web. "
    "\n\n"
    "REGRAS:\n"
    "- Quando o usuario pede codigo/programa: use criar_arquivo + executar_codigo\n"
    "- Quando pede pesquisa/informacao: use pesquisar_web ou buscar_noticias\n"
    "- Quando pede imagem: crie prompt em ingles e use gerar_imagem\n"
    "- Quando menciona tarefa/lembrete: use adicionar_tarefa\n"
    "- Quando diz 'fiz academia/treino': use registrar_treino\n"
    "- Quando fala de humor/sentimento: use registrar_humor\n"
    "- Quando pede emails: use ler_emails\n"
    "- Quando pede noticias/briefing: use buscar_noticias ou briefing_matinal\n"
    "- Quando pede review: use review_semanal\n"
    "- Quando pede dashboard/resumo do dia: use ver_dashboard\n"
    "- Para conversas casuais: responda naturalmente sem ferramentas\n"
    "\n"
    "Responda SEMPRE em portugues, de forma concisa e util.\n"
    "Se precisar de multiplas ferramentas, use todas que forem necessarias."
)


# ============================================================
# IRIS MAIN HANDLER
# ============================================================

async def iris_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main IRIS handler - processes ALL text messages."""
    user_msg = update.message.text.strip()
    if not user_msg:
        return

    # Save to history
    add_to_history("user", user_msg)

    # Build conversation context
    history = get_history()
    messages = [{"role": "system", "content": IRIS_SYSTEM}]

    # Add recent history for context (last 10 messages)
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})

    # If last message is not the current one, add it
    if not history or history[-1]["content"] != user_msg:
        messages.append({"role": "user", "content": user_msg})

    # Track images to send
    images_to_send = []

    # Function calling loop
    for round_n in range(8):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=IRIS_TOOLS,
                tool_choice="auto",
                max_tokens=4000,
                temperature=0.3,
            )
        except Exception as e:
            await update.message.reply_text(f"Erro: {e}")
            return

        msg = resp.choices[0].message

        if not msg.tool_calls:
            # Final response
            response = msg.content.strip() if msg.content else ""
            if response:
                add_to_history("assistant", response)
                # Send images first
                for img_path, img_url in images_to_send:
                    try:
                        if img_path and os.path.exists(img_path):
                            with open(img_path, "rb") as f:
                                await update.message.reply_photo(photo=f)
                        elif img_url:
                            r = http_requests.get(img_url, timeout=90)
                            if r.status_code == 200:
                                await update.message.reply_photo(photo=BytesIO(r.content))
                    except Exception:
                        pass
                # Send text
                for chunk in split_msg(response):
                    try:
                        await update.message.reply_text(chunk)
                    except Exception:
                        pass
            return

        # Execute tools
        messages.append(msg)
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except:
                fn_args = {}

            result = iris_execute_tool(fn_name, fn_args)

            # Check for image results
            if "IMAGE_PATH=" in str(result):
                m = re.search(r'IMAGE_PATH=(\S+)\s+IMAGE_URL=(\S+)', str(result))
                if m:
                    images_to_send.append((m.group(1), m.group(2)))

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)[:3000],
            })

    # If we hit max rounds, send what we have
    await update.message.reply_text("(processamento longo, tente novamente)")


# ============================================================
# POMODORO (still needs special handling for timers)
# ============================================================

async def pomodoro_done(context: CallbackContext):
    data = load_data("pomodoros"); hoje = today_str()
    if hoje not in data: data[hoje] = []
    task_name = context.job.data or "Foco"
    data[hoje].append({"hora": datetime.now(BRT).strftime("%H:%M"), "tarefa": task_name})
    save_data("pomodoros", data)
    await context.bot.send_message(chat_id=context.job.chat_id,
        text=f"POMODORO COMPLETO! Tarefa: {task_name}\nPomodoros hoje: {len(data[hoje])}")

async def cmd_foco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    minutos, tarefa = 25, "Foco geral"
    if args:
        try: minutos = int(args[0]); tarefa = " ".join(args[1:]) or "Foco geral"
        except: tarefa = " ".join(args)
    for j in context.job_queue.jobs():
        if j.name.startswith(f"pomo_{update.effective_chat.id}"): j.schedule_removal()
    context.job_queue.run_once(pomodoro_done, when=timedelta(minutes=minutos),
        chat_id=update.effective_chat.id,
        name=f"pomo_{update.effective_chat.id}_{minutos}", data=tarefa)
    fim = (datetime.now(BRT) + timedelta(minutes=minutos)).strftime("%H:%M")
    await update.message.reply_text(f"Pomodoro: {tarefa} ({minutos}min, termina {fim})")


# ============================================================
# NIGHT THINKING MODE
# ============================================================

async def night_thinking(context: CallbackContext):
    """Runs at 3 AM BRT - reviews the day and generates insights."""
    print("[NIGHT] Iniciando reflexao noturna...")

    chat_id = context.job.data
    if not chat_id:
        print("[NIGHT] Sem chat_id configurado")
        return

    # Gather all data from today
    hoje = today_str()
    ontem = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")

    history = get_history()
    diario = load_data("diario")
    tarefas = load_data("tarefas")
    humor = load_data("humor")
    treinos = load_data("treinos")
    pomos = load_data("pomodoros")
    metas = load_data("metas").get(week_key(), [])
    pensamentos_prev = load_data("pensamentos_noturnos")

    # Build context
    ctx = "=== DADOS DO DIA ===\n\n"

    ctx += "CONVERSAS RECENTES:\n"
    for h in history[-20:]:
        ctx += f"[{h.get('time','')}] {h['role']}: {h['content'][:200]}\n"

    ctx += f"\nDIARIO {hoje}:\n"
    for e in diario.get(hoje, []):
        ctx += f"  {e['texto'][:200]}\n"

    ctx += f"\nTAREFAS PENDENTES:\n"
    for t in tarefas.get("items", []):
        if not t["feita"]: ctx += f"  #{t['id']} {t['texto']}\n"

    ctx += f"\nTAREFAS CONCLUIDAS HOJE:\n"
    for t in tarefas.get("items", []):
        if t["feita"] and (t.get("feita_em") or "").startswith(hoje):
            ctx += f"  {t['texto']}\n"

    ctx += f"\nHUMOR: "
    for h in humor.get(hoje, []):
        ctx += f"{h['nivel']}/5 {h.get('nota','')} "
    ctx += "\n"

    ctx += f"TREINOS: "
    for t in treinos.get(hoje, []):
        ctx += f"{t['tipo']} "
    ctx += f"\nPOMODOROS: {len(pomos.get(hoje, []))}\n"

    ctx += f"\nMETAS SEMANA:\n"
    for m in metas:
        ctx += f"  [{'OK' if m['concluida'] else '...'}] {m['texto']}\n"

    ctx += f"\nPENSAMENTO ANTERIOR:\n{pensamentos_prev.get('ultimo', 'Nenhum')}\n"

    # Ask AI to think
    reflexao = chat_simple(
        system_prompt=(
            "Voce e IRIS, assistente pessoal inteligente. "
            "E 3 da manha e voce esta refletindo sobre o dia do Paulo. "
            "Analise os dados e gere:\n\n"
            "1. REFLEXAO DO DIA - O que aconteceu, padroes observados (2-3 frases)\n"
            "2. IDEIAS PARA AMANHA - 2-3 sugestoes praticas baseadas nos dados\n"
            "3. IDEIA DE MELHORIA DO BOT - Uma sugestao concreta para melhorar o sistema "
            "(nova funcionalidade, automacao, integracao). Pense como um product manager.\n"
            "4. TAREFAS SUGERIDAS - Se identificou algo que precisa ser feito\n\n"
            "Seja conciso, pratico e perspicaz. Portugues."
        ),
        user_message=ctx,
        max_tokens=2000,
    )

    # Save
    pensamentos = {
        "ultimo": reflexao,
        "data": hoje,
        "historico": pensamentos_prev.get("historico", []),
    }
    pensamentos["historico"].append({"data": hoje, "texto": reflexao[:500]})
    pensamentos["historico"] = pensamentos["historico"][-30:]  # Keep 30 days
    save_data("pensamentos_noturnos", pensamentos)

    print(f"[NIGHT] Reflexao salva ({len(reflexao)} chars)")

    # Send summary to Paulo
    try:
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=f"[IRIS - Reflexao Noturna]\n\n{reflexao}"
        )
    except Exception as e:
        print(f"[NIGHT] Erro ao enviar: {e}")


# ============================================================
# REMINDERS
# ============================================================

async def send_reminder(context: CallbackContext):
    await context.bot.send_message(chat_id=context.job.chat_id, text=context.job.data)

async def cmd_lembretes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("lembretes"); chat_id = update.effective_chat.id
    if not context.args:
        rems = data.get("ativos", [])
        if not rems:
            await update.message.reply_text(
                "Sem lembretes.\nExemplos:\n/lembretes treino 07:00\n/lembretes briefing 07:30\n/lembretes limpar")
            return
        msg = "LEMBRETES:\n" + "\n".join(f"  {i}. {r['tipo']} as {r['hora']}" for i, r in enumerate(rems, 1))
        await update.message.reply_text(msg); return
    if context.args[0] == "limpar":
        data["ativos"] = []; save_data("lembretes", data)
        for j in context.job_queue.jobs():
            if j.name.startswith("rem_"): j.schedule_removal()
        await update.message.reply_text("Lembretes removidos."); return
    if len(context.args) < 2: await update.message.reply_text("/lembretes [tipo] [HH:MM]"); return
    tipo = context.args[0]; hora_str = context.args[1]
    try: h, m = map(int, hora_str.split(":")); assert 0<=h<=23 and 0<=m<=59
    except: await update.message.reply_text("Hora invalida (HH:MM)"); return
    msgs = {"treino": "Hora do treino!", "diario": "Registre seu diario!",
        "agua": "Beba agua!", "humor": "Como voce esta?",
        "briefing": "Bom dia! Seu briefing esta pronto. Diga 'briefing'.",
        "email": "Confira seus emails!", "noticias": "Confira as noticias!"}
    if "ativos" not in data: data["ativos"] = []
    data["ativos"].append({"tipo": tipo, "hora": hora_str, "chat_id": chat_id})
    save_data("lembretes", data)
    context.job_queue.run_daily(send_reminder, time=dt_time(hour=h, minute=m, tzinfo=BRT),
        chat_id=chat_id, name=f"rem_{tipo}_{hora_str}",
        data=msgs.get(tipo, f"Lembrete: {tipo}"))
    await update.message.reply_text(f"Lembrete: {tipo} as {hora_str}")

def setup_saved_reminders(app):
    data = load_data("lembretes")
    msgs = {"treino": "Hora do treino!", "diario": "Registre seu diario!",
        "agua": "Beba agua!", "humor": "Como voce esta?",
        "briefing": "Bom dia! Diga 'briefing'.", "email": "Confira emails!",
        "noticias": "Noticias disponiveis!"}
    for r in data.get("ativos", []):
        try:
            h, m = map(int, r["hora"].split(":"))
            app.job_queue.run_daily(send_reminder, time=dt_time(hour=h, minute=m, tzinfo=BRT),
                chat_id=r["chat_id"], name=f"rem_{r['tipo']}_{r['hora']}",
                data=msgs.get(r["tipo"], f"Lembrete: {r['tipo']}"))
            print(f"[LEMBRETE] {r['tipo']} as {r['hora']}")
        except Exception as e: print(f"[LEMBRETE ERRO] {e}")


# ============================================================
# TELEGRAM HELPERS
# ============================================================

def split_msg(text, max_len=4000):
    text = str(text).strip()
    if not text: return ["(sem resposta)"]
    if len(text) <= max_len: return [text]
    chunks, cur = [], ""
    for par in text.split("\n\n"):
        if len(cur) + len(par) + 2 <= max_len: cur += par + "\n\n"
        else:
            if cur.strip(): chunks.append(cur.strip())
            if len(par) > max_len:
                for i in range(0, len(par), max_len): chunks.append(par[i:i+max_len])
                cur = ""
            else: cur = par + "\n\n"
    if cur.strip(): chunks.append(cur.strip())
    return chunks if chunks else [text[:max_len]]


# ============================================================
# MAIN
# ============================================================

async def error_handler(update, context):
    err = str(context.error)
    if "Conflict" in err or "terminated by other" in err: return
    print(f"[TELEGRAM ERROR] {err}")

def main():
    print("=" * 50)
    print("IRONCORE AGENTS v9.0 - IRIS")
    print("Agente Mestre + Linguagem Natural")
    print(f"LLM: DeepSeek V3")
    print(f"{datetime.now(BRT):%d/%m/%Y %H:%M:%S}")
    print("=" * 50)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Slash commands (shortcuts, still work)
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text(
        "=== IRIS v9.0 ===\n"
        "Assistente pessoal inteligente.\n\n"
        "Fale naturalmente comigo:\n"
        "- 'bom dia' -> briefing\n"
        "- 'me mostre as noticias'\n"
        "- 'tenho que fazer X' -> tarefa\n"
        "- 'fiz academia' -> treino\n"
        "- 'como estao meus emails?'\n"
        "- 'crie um programa que...'\n"
        "- 'gere uma imagem de...'\n"
        "- 'o que tem no reddit?'\n"
        "- 'como foi minha semana?'\n\n"
        "Atalhos: /foco /lembretes /status"
    )))
    app.add_handler(CommandHandler("foco", cmd_foco))
    app.add_handler(CommandHandler("lembretes", cmd_lembretes))
    app.add_handler(CommandHandler("status", lambda u, c: u.message.reply_text(
        f"=== IRIS v9.0 ===\n{datetime.now(BRT):%d/%m/%Y %H:%M}\n"
        f"Gmail: {'OK' if GMAIL_EMAIL else 'N/A'}\n"
        f"Chat ID: {u.effective_chat.id}\nOperacional.")))

    # IRIS handles ALL text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, iris_handle))

    app.add_error_handler(error_handler)

    # Restore reminders
    setup_saved_reminders(app)

    # Night thinking mode at 3:00 AM BRT
    target_chat = TELEGRAM_CHAT_ID or None
    if target_chat:
        app.job_queue.run_daily(
            night_thinking,
            time=dt_time(hour=3, minute=0, tzinfo=BRT),
            name="night_thinking",
            data=target_chat,
        )
        print(f"[NIGHT] Modo noturno ativo (3:00 AM) -> chat {target_chat}")
    else:
        print("[NIGHT] TELEGRAM_CHAT_ID nao configurado. Modo noturno desativado.")
        print("[NIGHT] Configure para ativar: use /status para ver seu chat_id")

    print(f"\nIRIS pronta. Linguagem natural ativa.\n")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
