# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v8.0
Roberto | Curioso | Marley + Vida + Noticias + Email + Reddit + LinkedIn
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
import email
from email.header import decode_header
from datetime import datetime, timedelta, timezone, time as dt_time
from io import BytesIO
from pathlib import Path

warnings.filterwarnings("ignore")
logging.getLogger("httpx").setLevel(logging.WARNING)

import requests as http_requests
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext

# ============================================================
# CONFIG
# ============================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Gmail IMAP
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Corporate email (optional)
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
# LLM
# ============================================================

def chat(system_prompt, user_message, max_tokens=4000):
    try:
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], max_tokens=max_tokens, temperature=0.3)
        return r.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERRO LLM] {e}"

def chat_with_tools(system_prompt, user_message, tools_def, tool_executor, max_rounds=6):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    for _ in range(max_rounds):
        try:
            r = client.chat.completions.create(
                model="deepseek-chat", messages=messages,
                tools=tools_def, tool_choice="auto",
                max_tokens=4000, temperature=0.3)
        except Exception as e:
            return f"[ERRO LLM] {e}"
        msg = r.choices[0].message
        if not msg.tool_calls:
            return msg.content.strip() if msg.content else "(sem resposta)"
        messages.append(msg)
        for tc in msg.tool_calls:
            try: fn_args = json.loads(tc.function.arguments)
            except: fn_args = {}
            result = tool_executor(tc.function.name, fn_args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)[:3000]})
    return "(max iteracoes)"


# ============================================================
# TOOLS
# ============================================================

def web_search(query, max_results=5):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({"titulo": r["title"], "resumo": r["body"][:300], "link": r["href"]})
        return results if results else [{"erro": f"Nenhum resultado: {query}"}]
    except Exception as e:
        return [{"erro": str(e)}]

def web_search_news(query, max_results=5):
    """Search specifically for news articles."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "titulo": r.get("title", ""),
                    "resumo": r.get("body", "")[:300],
                    "link": r.get("url", r.get("href", "")),
                    "fonte": r.get("source", ""),
                    "data": r.get("date", ""),
                })
        return results if results else [{"erro": f"Nenhuma noticia: {query}"}]
    except Exception as e:
        return [{"erro": str(e)}]

def fetch_page(url):
    try:
        resp = http_requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        from html.parser import HTMLParser
        class TE(HTMLParser):
            def __init__(self):
                super().__init__(); self.parts=[]; self.skip=False
            def handle_starttag(self, tag, a):
                if tag in ("script","style","nav","footer","header"): self.skip=True
            def handle_endtag(self, tag):
                if tag in ("script","style","nav","footer","header"): self.skip=False
            def handle_data(self, d):
                if not self.skip and d.strip(): self.parts.append(d.strip())
        p = TE(); p.feed(resp.text)
        return "\n".join(p.parts)[:4000]
    except Exception as e:
        return f"ERRO: {e}"

def generate_image(prompt):
    try:
        encoded = http_requests.utils.quote(prompt)
        seed = int(datetime.now().timestamp()) % 999999
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={seed}"
        print(f"[MARLEY] URL: {url[:120]}...")
        resp = http_requests.get(url, timeout=120, stream=True)
        print(f"[MARLEY] HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = b"".join(resp.iter_content(8192))
            if len(data) < 500:
                return f"ERRO: imagem pequena ({len(data)}b)"
            nm = f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
            fp = WS_MARLEY / nm; fp.write_bytes(data)
            return (url, str(fp), len(data))
        url2 = f"https://pollinations.ai/p/{encoded}"
        resp2 = http_requests.get(url2, timeout=120, stream=True)
        if resp2.status_code == 200:
            data = b"".join(resp2.iter_content(8192))
            if len(data) >= 500:
                fp = WS_MARLEY / f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
                fp.write_bytes(data)
                return (url2, str(fp), len(data))
        return f"ERRO: HTTP {resp.status_code} / {resp2.status_code}"
    except Exception as e:
        return f"ERRO: {e}"


# ============================================================
# EMAIL READER
# ============================================================

def decode_mime_header(raw):
    """Decode MIME encoded header to string."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def get_email_body(msg):
    """Extract text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
                except Exception:
                    pass
            elif ct == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body).strip()
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
        except Exception:
            body = str(msg.get_payload())
    return body[:2000]


def read_emails(email_addr, password, imap_server="imap.gmail.com", n=5, folder="INBOX"):
    """Read last N emails via IMAP. Returns list of dicts."""
    emails = []
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_addr, password)
        mail.select(folder, readonly=True)

        _, data = mail.search(None, "ALL")
        ids = data[0].split()
        if not ids:
            mail.logout()
            return [{"erro": "Caixa de entrada vazia"}]

        # Get last N
        recent_ids = ids[-n:]
        recent_ids.reverse()

        for eid in recent_ids:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            de = decode_mime_header(msg.get("From", ""))
            assunto = decode_mime_header(msg.get("Subject", "(sem assunto)"))
            data_email = msg.get("Date", "")
            body = get_email_body(msg)

            emails.append({
                "de": de[:100],
                "assunto": assunto[:200],
                "data": data_email[:30],
                "corpo": body[:500],
            })

        mail.logout()
    except imaplib.IMAP4.error as e:
        return [{"erro": f"Erro IMAP: {e}"}]
    except Exception as e:
        return [{"erro": f"Erro: {e}"}]

    return emails if emails else [{"erro": "Nenhum email encontrado"}]


# ============================================================
# REDDIT READER
# ============================================================

def fetch_reddit(subreddit="technology", sort="hot", limit=10):
    """Fetch top posts from a subreddit using public JSON API."""
    try:
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
        headers = {"User-Agent": "IRONCORE-Agent/1.0"}
        resp = http_requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return [{"erro": f"Reddit HTTP {resp.status_code}"}]

        data = resp.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            posts.append({
                "titulo": p.get("title", "")[:200],
                "score": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "selftext": p.get("selftext", "")[:300],
                "author": p.get("author", ""),
            })
        return posts if posts else [{"erro": "Nenhum post encontrado"}]
    except Exception as e:
        return [{"erro": str(e)}]


# ============================================================
# ROBERTO TOOLS
# ============================================================

ROBERTO_TOOLS_DEF = [
    {"type": "function", "function": {"name": "criar_arquivo",
        "description": "Cria arquivo no workspace",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string"}, "content": {"type": "string"}},
            "required": ["filename", "content"]}}},
    {"type": "function", "function": {"name": "executar_python",
        "description": "Executa codigo Python",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "executar_bash",
        "description": "Executa comando shell",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "ler_arquivo",
        "description": "Le arquivo do workspace",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "listar_workspace",
        "description": "Lista arquivos",
        "parameters": {"type": "object", "properties": {}}}},
]

def roberto_tool_executor(fn_name, fn_args):
    if fn_name == "criar_arquivo":
        fn, ct = fn_args.get("filename", "out.py"), fn_args.get("content", "")
        try:
            p = WS_ROBERTO / fn; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ct, encoding="utf-8"); return f"OK: {fn} ({len(ct)}b)"
        except Exception as e: return f"ERRO: {e}"
    elif fn_name == "executar_python":
        code = fn_args.get("code", "")
        try:
            tmp = WS_ROBERTO / "_run.py"; tmp.write_text(code, encoding="utf-8")
            r = subprocess.run(["python3", str(tmp)], capture_output=True, text=True,
                timeout=30, cwd=str(WS_ROBERTO))
            return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
        except subprocess.TimeoutExpired: return "ERRO: timeout"
        except Exception as e: return f"ERRO: {e}"
    elif fn_name == "executar_bash":
        cmd = fn_args.get("command", "")
        if any(x in cmd for x in ["rm -rf /", "mkfs", ":(){ "]): return "ERRO: bloqueado"
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=str(WS_ROBERTO))
            return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
        except Exception as e: return f"ERRO: {e}"
    elif fn_name == "ler_arquivo":
        fn = fn_args.get("filename", "")
        try:
            p = WS_ROBERTO / fn
            if not p.exists(): return f"ERRO: nao encontrado: {fn}"
            return p.read_text(encoding="utf-8")[:4000]
        except Exception as e: return f"ERRO: {e}"
    elif fn_name == "listar_workspace":
        fs = [f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")]
        return "\n".join(str(f.relative_to(WS_ROBERTO)) for f in fs[:30]) if fs else "Vazio"
    return f"ERRO: desconhecido: {fn_name}"


# ============================================================
# TELEGRAM HELPERS
# ============================================================

def split_msg(text, max_len=4000):
    text = str(text).strip()
    if not text: return ["(sem resposta)"]
    if len(text) <= max_len: return [text]
    chunks, cur = [], ""
    for par in text.split("\n\n"):
        if len(cur) + len(par) + 2 <= max_len:
            cur += par + "\n\n"
        else:
            if cur.strip(): chunks.append(cur.strip())
            if len(par) > max_len:
                for i in range(0, len(par), max_len): chunks.append(par[i:i+max_len])
                cur = ""
            else: cur = par + "\n\n"
    if cur.strip(): chunks.append(cur.strip())
    return chunks if chunks else [text[:max_len]]

async def send_long(update, text):
    for i, chunk in enumerate(split_msg(text)):
        try:
            pref = f"(parte {i+1})\n\n" if i > 0 else ""
            await update.message.reply_text(pref + chunk)
        except: pass

async def send_image(update, url=None, local_path=None):
    if local_path:
        try:
            if os.path.exists(local_path) and os.path.getsize(local_path) > 500:
                with open(local_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Imagem por Marley")
                return True
        except: pass
    if url:
        try:
            resp = http_requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 500:
                await update.message.reply_photo(photo=BytesIO(resp.content), caption="Imagem por Marley")
                return True
        except: pass
        await update.message.reply_text(f"Imagem:\n{url}"); return True
    return False


# ============================================================
# AGENT COMMANDS
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "=== IRONCORE AGENTS v8.0 ===\n"
        "Assistente Pessoal Completo\n\n"
        "--- AGENTES ---\n"
        "/roberto [tarefa]\n"
        "/curioso [pergunta]\n"
        "/marley [descricao]\n"
        "/team [projeto]\n\n"
        "--- INFORMACAO ---\n"
        "/noticias [categoria]\n"
        "/email [n] - Ultimos emails\n"
        "/reddit [subreddit]\n"
        "/linkedin [tema]\n"
        "/briefing - Resumo matinal completo\n\n"
        "--- PRODUTIVIDADE ---\n"
        "/diario /foco /pausa\n"
        "/tarefa /tarefas /feito\n"
        "/meta /metas /review\n\n"
        "--- SAUDE ---\n"
        "/treino /humor\n\n"
        "--- GERAL ---\n"
        "/dash /status /lembretes\n"
        "/workspace /limpar\n\n"
        "Dica: /briefing pela manha, /review no fim de semana"
    )


async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/roberto [tarefa]"); return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Roberto] {tarefa}\nTrabalhando...")
    result = chat_with_tools(
        "Voce e Roberto, engenheiro senior. Use ferramentas para criar e testar codigo. NUNCA de passo-a-passo.",
        f"TAREFA: {tarefa}", ROBERTO_TOOLS_DEF, roberto_tool_executor, 8)
    await send_long(update, f"[Roberto]\n\n{result}")


async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/curioso [pergunta]"); return
    pergunta = " ".join(context.args)
    await update.message.reply_text(f"[Curioso] {pergunta}\nBuscando...")
    kw = chat("Extract 2-5 search keywords. Return ONLY keywords.", pergunta, 50)
    sq = kw if not kw.startswith("[ERRO") else pergunta
    results = web_search(sq)
    stxt = ""
    for i, r in enumerate(results, 1):
        if "erro" in r: stxt += f"\n{r['erro']}"
        else: stxt += f"\n{i}. {r['titulo']}\n{r['resumo']}\n{r['link']}\n"
    summary = chat("Responda SOMENTE com dados da busca. Cite fontes. NUNCA invente.",
        f"PERGUNTA: {pergunta}\n\nRESULTADOS:\n{stxt}")
    await send_long(update, f"[Curioso]\n\n{summary}")


async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/marley [descricao]"); return
    pedido = " ".join(context.args)
    await update.message.reply_text(f"[Marley] {pedido}\nGerando...")
    prompt_en = chat(
        "Create detailed image prompt in ENGLISH (50-100 words). Subject, style, lighting. "
        "Add 'highly detailed, 8k'. Return ONLY the prompt.",
        f"Create image prompt for: {pedido}", 300)
    if prompt_en.startswith("[ERRO"): await update.message.reply_text(f"[Marley] {prompt_en}"); return
    result = generate_image(prompt_en)
    if isinstance(result, tuple):
        sent = await send_image(update, url=result[0], local_path=result[1])
        if sent: await update.message.reply_text(f"[Marley] ({result[2]:,} bytes)")
    else: await update.message.reply_text(f"[Marley] {result}")


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/team [projeto]"); return
    projeto = " ".join(context.args)
    await update.message.reply_text(f"[Team] {projeto}\n3 agentes...")
    results = web_search(projeto)
    stxt = "".join(f"- {r['titulo']}: {r['resumo'][:150]}\n" for r in results if "erro" not in r)
    pesquisa = chat("Resuma os resultados para um projeto.", f"PROJETO: {projeto}\n{stxt}", 1500)
    codigo = chat_with_tools("Voce e Roberto. Crie codigo com ferramentas.",
        f"PROJETO: {projeto}\nPESQUISA:\n{pesquisa[:1000]}", ROBERTO_TOOLS_DEF, roberto_tool_executor, 6)
    prompt_en = chat("Create image prompt in English (50 words). Return ONLY prompt.", f"Project: {projeto}", 200)
    img = generate_image(prompt_en)
    if isinstance(img, tuple): await send_image(update, url=img[0], local_path=img[1])
    await send_long(update, f"[Team]\n\n=== PESQUISA ===\n{pesquisa}\n\n=== CODIGO ===\n{codigo}")


# ============================================================
# NEWS
# ============================================================

NEWS_CATEGORIES = {
    "brasil": ["Brasil economia politica hoje", "Brasil noticias principais hoje"],
    "tech": ["inteligencia artificial novidades 2026", "tecnologia noticias hoje"],
    "mundo": ["world news today", "noticias internacionais hoje"],
    "ia": ["AI artificial intelligence breakthroughs 2026", "LLM GPT Claude DeepSeek news"],
}

async def cmd_noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = context.args if context.args else ["brasil", "tech", "mundo"]

    valid_cats = []
    for c in cats:
        c_lower = c.lower()
        if c_lower in NEWS_CATEGORIES:
            valid_cats.append(c_lower)
        else:
            valid_cats.append("brasil")

    await update.message.reply_text(
        f"[Noticias] Buscando: {', '.join(valid_cats)}...")

    all_news = []
    for cat in valid_cats:
        queries = NEWS_CATEGORIES.get(cat, NEWS_CATEGORIES["brasil"])
        for q in queries:
            results = web_search_news(q, max_results=5)
            for r in results:
                if "erro" not in r:
                    r["categoria"] = cat
                    all_news.append(r)

    if not all_news:
        await update.message.reply_text("Nenhuma noticia encontrada.")
        return

    # Format for AI summary
    news_text = ""
    for i, n in enumerate(all_news[:20], 1):
        news_text += (
            f"\n[{n['categoria'].upper()}] {n['titulo']}\n"
            f"Fonte: {n.get('fonte', 'N/A')} | {n.get('data', '')}\n"
            f"{n['resumo']}\n{n['link']}\n"
        )

    summary = chat(
        system_prompt=(
            "Voce e um editor de noticias. Crie um BRIEFING conciso em portugues. "
            "Organize por categoria (BRASIL, TECH, MUNDO, IA). "
            "Para cada noticia: titulo + 1-2 frases de resumo + fonte. "
            "Maximo 5 noticias por categoria. "
            "No final, uma frase com o destaque do dia."
        ),
        user_message=f"Noticias coletadas:\n{news_text}\n\nCrie o briefing.",
        max_tokens=3000,
    )

    # Save
    data = load_data("noticias")
    data[today_str()] = {"hora": now_str(), "categorias": valid_cats, "resumo": summary[:2000]}
    save_data("noticias", data)

    await send_long(update, f"[Noticias {today_str()}]\n\n{summary}")


# ============================================================
# EMAIL
# ============================================================

async def cmd_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []

    # Determine which account and how many
    conta = "gmail"
    n = 5
    for a in args:
        if a.lower() in ("corp", "corporativo", "trabalho", "brasforma"):
            conta = "corp"
        else:
            try: n = int(a)
            except: pass

    n = min(max(n, 1), 20)

    if conta == "gmail":
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            await update.message.reply_text(
                "Gmail nao configurado.\n\n"
                "Configure no Render (Environment):\n"
                "GMAIL_EMAIL = seu@gmail.com\n"
                "GMAIL_APP_PASSWORD = senha de app\n\n"
                "Para gerar App Password:\n"
                "1. myaccount.google.com/security\n"
                "2. Verificacao em 2 etapas (ativar)\n"
                "3. Senhas de app > gerar nova\n"
                "4. Copie a senha de 16 caracteres")
            return
        email_addr = GMAIL_EMAIL
        password = GMAIL_APP_PASSWORD
        server = "imap.gmail.com"
    else:
        if not CORP_EMAIL or not CORP_PASSWORD:
            await update.message.reply_text(
                "Email corporativo nao configurado.\n\n"
                "Configure no Render:\n"
                "CORP_EMAIL = seu@empresa.com\n"
                "CORP_PASSWORD = senha\n"
                "CORP_IMAP_SERVER = imap.servidor.com")
            return
        email_addr = CORP_EMAIL
        password = CORP_PASSWORD
        server = CORP_IMAP_SERVER or "imap.gmail.com"

    await update.message.reply_text(f"[Email] Lendo {n} emails de {conta}...")

    emails = read_emails(email_addr, password, server, n)

    if emails and "erro" in emails[0]:
        await update.message.reply_text(f"[Email] {emails[0]['erro']}")
        return

    # Format for AI summary
    email_text = ""
    for i, e in enumerate(emails, 1):
        email_text += (
            f"\n--- Email {i} ---\n"
            f"De: {e['de']}\n"
            f"Assunto: {e['assunto']}\n"
            f"Data: {e['data']}\n"
            f"Corpo: {e['corpo'][:300]}\n"
        )

    summary = chat(
        system_prompt=(
            "Voce e um assistente de email. Resuma os emails recebidos em portugues. "
            "Para cada email: remetente, assunto, resumo em 1-2 frases, e se requer acao. "
            "No final, liste os que precisam de resposta urgente. "
            "Seja conciso e pratico."
        ),
        user_message=f"Emails recebidos ({conta}):\n{email_text}\n\nResuma de forma pratica.",
        max_tokens=2000,
    )

    await send_long(update, f"[Email - {conta.upper()}]\n\n{summary}")


# ============================================================
# REDDIT
# ============================================================

REDDIT_DEFAULTS = {
    "tech": "technology",
    "ia": "artificial",
    "python": "Python",
    "brasil": "brasil",
    "news": "worldnews",
    "dev": "programming",
    "startup": "startups",
    "finance": "finance",
}

async def cmd_reddit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or ["tech"]
    sub = args[0].lower()

    # Map aliases
    subreddit = REDDIT_DEFAULTS.get(sub, sub)

    await update.message.reply_text(f"[Reddit] r/{subreddit} ...")

    posts = fetch_reddit(subreddit, "hot", 10)

    if posts and "erro" in posts[0]:
        await update.message.reply_text(f"[Reddit] {posts[0]['erro']}")
        return

    # Format
    posts_text = ""
    for i, p in enumerate(posts[:10], 1):
        posts_text += (
            f"\n{i}. [{p['score']} pts, {p['comments']} comments] {p['titulo']}\n"
            f"   {p['selftext'][:150]}\n"
            f"   {p['url']}\n"
        )

    summary = chat(
        system_prompt=(
            "Voce e um curador de conteudo do Reddit. "
            "Resuma os posts mais relevantes em portugues. "
            "Para cada post relevante: titulo traduzido + por que importa em 1 frase. "
            "Destaque os 3 mais importantes. Ignore posts irrelevantes ou memes."
        ),
        user_message=f"Posts de r/{subreddit}:\n{posts_text}\n\nResuma os destaques.",
        max_tokens=2000,
    )

    await send_long(update, f"[Reddit - r/{subreddit}]\n\n{summary}")


# ============================================================
# LINKEDIN (via web search)
# ============================================================

async def cmd_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tema = " ".join(context.args) if context.args else "business trends technology"
    await update.message.reply_text(f"[LinkedIn] Buscando tendencias: {tema}...")

    # Search for LinkedIn-style content
    results1 = web_search(f"LinkedIn trending {tema} 2026", 5)
    results2 = web_search(f"{tema} industry insights trends", 5)

    all_results = results1 + results2
    rtxt = ""
    for r in all_results:
        if "erro" not in r:
            rtxt += f"- {r['titulo']}: {r['resumo'][:200]}\n{r['link']}\n\n"

    if not rtxt:
        await update.message.reply_text("[LinkedIn] Nenhum resultado encontrado.")
        return

    summary = chat(
        system_prompt=(
            "Voce e um analista de tendencias profissionais (estilo LinkedIn). "
            "Com base nos resultados de busca, crie um resumo de tendencias. "
            "Formato: 3-5 tendencias/insights com explicacao breve. "
            "Tom profissional, relevante para executivos e empreendedores. "
            "Responda em portugues."
        ),
        user_message=f"Tema: {tema}\n\nResultados:\n{rtxt}\n\nCrie o resumo de tendencias.",
        max_tokens=2000,
    )

    await send_long(update, f"[LinkedIn Trends - {tema}]\n\n{summary}")


# ============================================================
# MORNING BRIEFING
# ============================================================

async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("[Briefing] Preparando seu resumo matinal...")

    parts = []

    # 1. NEWS
    all_news = []
    for cat in ["brasil", "tech", "mundo"]:
        for q in NEWS_CATEGORIES[cat]:
            for r in web_search_news(q, 3):
                if "erro" not in r:
                    r["cat"] = cat
                    all_news.append(r)

    news_txt = ""
    for n in all_news[:15]:
        news_txt += f"[{n['cat'].upper()}] {n['titulo']} - {n['resumo'][:100]}\n"

    # 2. REDDIT top posts
    reddit_txt = ""
    for sub in ["technology", "worldnews"]:
        posts = fetch_reddit(sub, "hot", 5)
        for p in posts[:5]:
            if "erro" not in p:
                reddit_txt += f"[r/{sub}] {p['titulo']} ({p['score']} pts)\n"

    # 3. EMAILS (if configured)
    email_txt = ""
    if GMAIL_EMAIL and GMAIL_APP_PASSWORD:
        emails = read_emails(GMAIL_EMAIL, GMAIL_APP_PASSWORD, "imap.gmail.com", 5)
        for e in emails:
            if "erro" not in e:
                email_txt += f"De: {e['de'][:30]} | {e['assunto'][:80]}\n"

    # 4. TASKS
    tarefas = load_data("tarefas")
    pendentes = [t for t in tarefas.get("items", []) if not t["feita"]]
    task_txt = "\n".join(f"#{t['id']} {t['texto']}" for t in pendentes[:10])

    # 5. WEEKLY GOALS
    metas_data = load_data("metas")
    metas = metas_data.get(week_key(), [])
    meta_txt = "\n".join(f"[{'OK' if m['concluida'] else '...'}] {m['texto']}" for m in metas)

    # 6. MOOD/ENERGY yesterday
    humor = load_data("humor")
    ontem = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
    humor_txt = ""
    for h in humor.get(ontem, []):
        humor_txt += f"{h['nivel']}/5 {h.get('nota', '')}\n"

    # Compile and send to AI
    full_context = (
        f"=== NOTICIAS ===\n{news_txt}\n\n"
        f"=== REDDIT ===\n{reddit_txt}\n\n"
        f"=== EMAILS NAO LIDOS ===\n{email_txt or '(nao configurado)'}\n\n"
        f"=== TAREFAS PENDENTES ===\n{task_txt or 'Nenhuma'}\n\n"
        f"=== METAS DA SEMANA ===\n{meta_txt or 'Nenhuma'}\n\n"
        f"=== HUMOR ONTEM ===\n{humor_txt or 'Nao registrado'}\n"
    )

    briefing = chat(
        system_prompt=(
            "Voce e um assistente pessoal criando o BRIEFING MATINAL. "
            "Estruture assim:\n"
            "1. BOM DIA + data + frase motivacional curta\n"
            "2. TOP 5 NOTICIAS (1 frase cada, mais importante primeiro)\n"
            "3. REDDIT DESTAQUE (2-3 posts relevantes)\n"
            "4. EMAILS (resumo se houver, destaque urgentes)\n"
            "5. TAREFAS DO DIA (liste pendentes)\n"
            "6. METAS DA SEMANA (progresso)\n"
            "7. FRASE DO DIA (inspiracional, curta)\n"
            "Seja conciso, pratico, energizante. Responda em portugues."
        ),
        user_message=full_context,
        max_tokens=3000,
    )

    await send_long(update, f"[Briefing Matinal]\n\n{briefing}")


# ============================================================
# JOURNALING
# ============================================================

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("diario")
    hoje = today_str()
    if not context.args:
        entries = data.get(hoje, [])
        if not entries:
            await update.message.reply_text(f"Diario {hoje}: vazio.\nUse: /diario [texto]"); return
        msg = f"=== Diario {hoje} ===\n\n"
        for i, e in enumerate(entries, 1):
            msg += f"{i}. [{e['hora']}] {e['texto']}\n\n"
        await update.message.reply_text(msg); return
    texto = " ".join(context.args)
    if hoje not in data: data[hoje] = []
    data[hoje].append({"hora": datetime.now(BRT).strftime("%H:%M"), "texto": texto})
    save_data("diario", data)
    await update.message.reply_text(f"Diario registrado ({len(data[hoje])}a entrada).\n\"{texto[:100]}\"")


# ============================================================
# POMODORO
# ============================================================

async def pomodoro_done(context: CallbackContext):
    data = load_data("pomodoros")
    hoje = today_str()
    if hoje not in data: data[hoje] = []
    task_name = context.job.data or "Foco"
    data[hoje].append({
        "hora": datetime.now(BRT).strftime("%H:%M"),
        "tarefa": task_name,
    })
    save_data("pomodoros", data)
    await context.bot.send_message(chat_id=context.job.chat_id,
        text=f"POMODORO COMPLETO!\nTarefa: {task_name}\nPausa 5min.\nPomodoros hoje: {len(data[hoje])}")

async def cmd_foco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    minutos, tarefa = 25, "Foco geral"
    if args:
        try: minutos = int(args[0]); tarefa = " ".join(args[1:]) or "Foco geral"
        except ValueError: tarefa = " ".join(args)
    if minutos < 1 or minutos > 120:
        await update.message.reply_text("1-120 minutos."); return
    for j in context.job_queue.jobs():
        if j.name.startswith(f"pomo_{update.effective_chat.id}"): j.schedule_removal()
    context.job_queue.run_once(pomodoro_done, when=timedelta(minutes=minutos),
        chat_id=update.effective_chat.id,
        name=f"pomo_{update.effective_chat.id}_{minutos}", data=tarefa)
    fim = (datetime.now(BRT) + timedelta(minutes=minutos)).strftime("%H:%M")
    await update.message.reply_text(
        f"POMODORO INICIADO\nTarefa: {tarefa}\nDuracao: {minutos}min\nTermina: {fim}")

async def cmd_pausa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    removed = False
    for j in context.job_queue.jobs():
        if j.name.startswith(f"pomo_{update.effective_chat.id}"):
            j.schedule_removal(); removed = True
    await update.message.reply_text("Pomodoro cancelado." if removed else "Nenhum pomodoro ativo.")


# ============================================================
# TASKS
# ============================================================

async def cmd_tarefa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/tarefa [descricao]"); return
    data = load_data("tarefas")
    if "items" not in data: data["items"] = []; data["next_id"] = 1
    texto = " ".join(context.args)
    tid = data["next_id"]
    data["items"].append({"id": tid, "texto": texto, "criada": now_str(), "feita": False, "feita_em": None})
    data["next_id"] = tid + 1
    save_data("tarefas", data)
    await update.message.reply_text(f"Tarefa #{tid}: \"{texto}\"")

async def cmd_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("tarefas")
    items = data.get("items", [])
    pendentes = [t for t in items if not t["feita"]]
    feitas_hoje = [t for t in items if t["feita"] and (t.get("feita_em") or "").startswith(today_str())]
    if not pendentes and not feitas_hoje:
        await update.message.reply_text("Nenhuma tarefa.\n/tarefa [texto]"); return
    msg = "=== TAREFAS ===\n\n"
    if pendentes:
        msg += "PENDENTES:\n"
        for t in pendentes: msg += f"  #{t['id']} - {t['texto']}\n"
    if feitas_hoje:
        msg += f"\nHOJE ({len(feitas_hoje)}):\n"
        for t in feitas_hoje: msg += f"  #{t['id']} - {t['texto']}\n"
    msg += f"\n{len(pendentes)} pendente(s) | /feito [n]"
    await update.message.reply_text(msg)

async def cmd_feito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("/feito [numero]"); return
    try: tid = int(context.args[0])
    except: await update.message.reply_text("/feito [numero]"); return
    data = load_data("tarefas")
    for t in data.get("items", []):
        if t["id"] == tid and not t["feita"]:
            t["feita"] = True; t["feita_em"] = now_str(); save_data("tarefas", data)
            pend = len([x for x in data["items"] if not x["feita"]])
            await update.message.reply_text(f"#{tid} concluida!\n\"{t['texto']}\"\n{pend} pendente(s)")
            return
    await update.message.reply_text(f"#{tid} nao encontrada.")


# ============================================================
# WEEKLY GOALS
# ============================================================

async def cmd_meta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("/meta [texto]"); return
    data = load_data("metas"); wk = week_key()
    if wk not in data: data[wk] = []
    texto = " ".join(context.args)
    data[wk].append({"texto": texto, "criada": now_str(), "concluida": False})
    save_data("metas", data)
    await update.message.reply_text(f"Meta semanal ({len(data[wk])}): \"{texto}\"")

async def cmd_metas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("metas"); wk = week_key(); metas = data.get(wk, [])
    if not metas: await update.message.reply_text(f"Sem metas ({wk}).\n/meta [texto]"); return
    msg = f"=== METAS {wk} ===\n\n"
    for i, m in enumerate(metas, 1):
        msg += f"  {i}. [{'OK' if m['concluida'] else '...'}] {m['texto']}\n"
    msg += f"\n{sum(1 for m in metas if m['concluida'])}/{len(metas)}"
    await update.message.reply_text(msg)


# ============================================================
# EXERCISE & MOOD
# ============================================================

async def cmd_treino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("treinos"); hoje = today_str()
    if not context.args:
        all_t = []
        for d, ts in sorted(data.items(), reverse=True)[:7]:
            for t in ts: all_t.append(f"  [{d} {t['hora']}] {t['tipo']}")
        if not all_t: await update.message.reply_text("Nenhum treino.\n/treino [tipo]"); return
        await update.message.reply_text("=== TREINOS 7 DIAS ===\n\n" + "\n".join(all_t)); return
    tipo = " ".join(context.args)
    if hoje not in data: data[hoje] = []
    data[hoje].append({"hora": datetime.now(BRT).strftime("%H:%M"), "tipo": tipo})
    save_data("treinos", data)
    wk = sum(len(data.get((datetime.now(BRT)-timedelta(days=i)).strftime("%Y-%m-%d"), [])) for i in range(7))
    await update.message.reply_text(f"Treino: {tipo}\nSemana: {wk} sessao(es)")

async def cmd_humor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("humor"); hoje = today_str()
    if not context.args:
        entries = []
        for d in sorted(data.keys(), reverse=True)[:7]:
            for e in data[d]:
                entries.append(f"  [{d} {e['hora']}] {e['nivel']}/5 - {e.get('nota', '')}")
        if not entries: await update.message.reply_text("Nenhum registro.\n/humor [1-5] [nota]"); return
        await update.message.reply_text("=== HUMOR ===\n\n" + "\n".join(entries)); return
    try:
        nivel = int(context.args[0])
        assert 1 <= nivel <= 5
    except: await update.message.reply_text("/humor [1-5] [nota]"); return
    nota = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    if hoje not in data: data[hoje] = []
    data[hoje].append({"hora": datetime.now(BRT).strftime("%H:%M"), "nivel": nivel, "nota": nota})
    save_data("humor", data)
    labels = ["", "1/5 pessimo", "2/5 ruim", "3/5 neutro", "4/5 bom", "5/5 otimo"]
    await update.message.reply_text(f"Humor: {labels[nivel]}\n{nota}")


# ============================================================
# DASHBOARD
# ============================================================

async def cmd_dash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = today_str(); agora = datetime.now(BRT).strftime("%H:%M")
    diario = load_data("diario").get(hoje, [])
    tarefas = load_data("tarefas")
    pend = [t for t in tarefas.get("items", []) if not t["feita"]]
    feitas = [t for t in tarefas.get("items", []) if t["feita"] and (t.get("feita_em") or "").startswith(hoje)]
    pomos = load_data("pomodoros").get(hoje, [])
    treinos = load_data("treinos").get(hoje, [])
    humor = load_data("humor").get(hoje, [])
    metas_data = load_data("metas"); metas = metas_data.get(week_key(), [])
    metas_ok = sum(1 for m in metas if m["concluida"])

    msg = f"=== DASHBOARD {hoje} ({agora}) ===\n\n"
    msg += f"Diario: {len(diario)} entrada(s)\n"
    for e in diario[-2:]: msg += f"  [{e['hora']}] {e['texto'][:50]}\n"
    msg += f"\nTarefas: {len(feitas)} feita(s) / {len(pend)} pendente(s)\n"
    for t in pend[:5]: msg += f"  #{t['id']} {t['texto'][:40]}\n"
    msg += f"\nPomodoros: {len(pomos)}\n"
    msg += f"Treino: {len(treinos)} sessao(es)\n"
    if humor:
        h = humor[-1]; msg += f"Humor: {h['nivel']}/5 {h.get('nota', '')}\n"
    else: msg += "Humor: --\n"
    msg += f"\nMetas: {metas_ok}/{len(metas)}\n"
    for m in metas: msg += f"  [{'OK' if m['concluida'] else '...'}] {m['texto'][:40]}\n"
    await update.message.reply_text(msg)


# ============================================================
# REVIEW
# ============================================================

async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("[Review] Analisando semana...")
    days = [(datetime.now(BRT)-timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    diario = load_data("diario"); tarefas = load_data("tarefas")
    pomos = load_data("pomodoros"); treinos = load_data("treinos")
    humor = load_data("humor"); metas_data = load_data("metas")
    ctx = "DADOS DA SEMANA:\n\n"
    ctx += "DIARIO:\n"
    for d in days:
        for e in diario.get(d, []): ctx += f"  {d} [{e['hora']}] {e['texto'][:150]}\n"
    ctx += "\nTAREFAS CONCLUIDAS:\n"
    for t in tarefas.get("items", []):
        if t["feita"] and (t.get("feita_em") or "")[:10] in days: ctx += f"  {t['feita_em']}: {t['texto']}\n"
    ctx += f"\nPENDENTES: {len([t for t in tarefas.get('items', []) if not t['feita']])}\n"
    total_p = sum(len(pomos.get(d, [])) for d in days)
    ctx += f"\nPOMODOROS: {total_p}\n"
    for d in days:
        for t in treinos.get(d, []): ctx += f"TREINO: {d} {t['tipo']}\n"
    for d in days:
        for h in humor.get(d, []): ctx += f"HUMOR: {d} {h['nivel']}/5 {h.get('nota','')}\n"
    metas = metas_data.get(week_key(), [])
    for m in metas: ctx += f"META: [{'OK' if m['concluida'] else 'PENDENTE'}] {m['texto']}\n"
    review = chat(
        "Voce e um coach pessoal. Analise a semana e de: "
        "1. RESUMO (2-3 frases) 2. DESTAQUES 3. PONTOS DE ATENCAO "
        "4. SUGESTOES 5. NOTA (0-10). Portugues. Motivador e pratico.",
        ctx, 2000)
    await send_long(update, f"[Review Semanal]\n\n{review}")


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
                "Sem lembretes.\n\n"
                "/lembretes treino 07:00\n"
                "/lembretes diario 22:00\n"
                "/lembretes briefing 07:30\n"
                "/lembretes limpar")
            return
        msg = "=== LEMBRETES ===\n\n"
        for i, r in enumerate(rems, 1): msg += f"  {i}. {r['tipo']} as {r['hora']}\n"
        msg += "\n/lembretes limpar"
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
    msgs = {
        "treino": "Hora do treino! /treino [tipo]",
        "diario": "Hora do diario! /diario [texto]",
        "agua": "Beba agua!",
        "humor": "Como voce esta? /humor [1-5]",
        "foco": "Hora de focar! /foco",
        "review": "Review semanal! /review",
        "briefing": "Bom dia! Use /briefing para seu resumo matinal.",
        "email": "Confira seus emails! /email",
        "noticias": "Confira as noticias! /noticias",
    }
    msg_text = msgs.get(tipo, f"Lembrete: {tipo}")
    if "ativos" not in data: data["ativos"] = []
    data["ativos"].append({"tipo": tipo, "hora": hora_str, "chat_id": chat_id})
    save_data("lembretes", data)
    context.job_queue.run_daily(send_reminder, time=dt_time(hour=h, minute=m, tzinfo=BRT),
        chat_id=chat_id, name=f"rem_{tipo}_{hora_str}", data=msg_text)
    await update.message.reply_text(f"Lembrete: {tipo} as {hora_str} diariamente.")

def setup_saved_reminders(app):
    data = load_data("lembretes")
    msgs = {"treino": "Hora do treino!", "diario": "Hora do diario!",
        "agua": "Beba agua!", "humor": "Como voce esta? /humor [1-5]",
        "foco": "Hora de focar!", "review": "Review semanal!",
        "briefing": "Bom dia! /briefing", "email": "Confira emails! /email",
        "noticias": "Confira noticias! /noticias"}
    for r in data.get("ativos", []):
        try:
            h, m = map(int, r["hora"].split(":"))
            app.job_queue.run_daily(send_reminder, time=dt_time(hour=h, minute=m, tzinfo=BRT),
                chat_id=r["chat_id"], name=f"rem_{r['tipo']}_{r['hora']}",
                data=msgs.get(r["tipo"], f"Lembrete: {r['tipo']}"))
            print(f"[LEMBRETE] {r['tipo']} as {r['hora']}")
        except Exception as e: print(f"[LEMBRETE ERRO] {e}")


# ============================================================
# UTILITY
# ============================================================

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = len([f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")])
    cc = len([f for f in WS_CURIOSO.rglob("*") if f.is_file()])
    mc = len([f for f in WS_MARLEY.rglob("*") if f.is_file()])
    pend = len([t for t in load_data("tarefas").get("items", []) if not t["feita"]])
    gmail_ok = "OK" if GMAIL_EMAIL and GMAIL_APP_PASSWORD else "nao configurado"
    corp_ok = "OK" if CORP_EMAIL and CORP_PASSWORD else "nao configurado"
    await update.message.reply_text(
        f"=== IRONCORE AGENTS v8.0 ===\n"
        f"LLM: DeepSeek V3\n{datetime.now(BRT):%d/%m/%Y %H:%M}\n\n"
        f"[Roberto] ONLINE ({rc} arq)\n"
        f"[Curioso] ONLINE ({cc} arq)\n"
        f"[Marley] ONLINE ({mc} arq)\n\n"
        f"Gmail: {gmail_ok}\nCorp: {corp_ok}\n"
        f"Tarefas: {pend} pendente(s)\nOperacional.")

async def cmd_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "=== WORKSPACES ===\n\n"
    for nm, ws in [("Roberto", WS_ROBERTO), ("Curioso", WS_CURIOSO), ("Marley", WS_MARLEY)]:
        fs = [f for f in ws.rglob("*") if f.is_file() and not f.name.startswith("_")]
        msg += f"--- {nm} ---\n"
        for f in fs[:10]: msg += f"  {f.relative_to(ws)} ({f.stat().st_size:,}b)\n"
        if not fs: msg += "  (vazio)\n"
        msg += "\n"
    await update.message.reply_text(msg)

async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = 0
    for ws in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY):
        for f in ws.rglob("*"):
            if f.is_file(): f.unlink(); n += 1
    await update.message.reply_text(f"{n} arquivo(s) removido(s).")


# ============================================================
# MAIN
# ============================================================

async def error_handler(update, context):
    err = str(context.error)
    if "Conflict" in err or "terminated by other" in err: return
    print(f"[TELEGRAM ERROR] {err}")

def main():
    print("=" * 50)
    print("IRONCORE AGENTS v8.0")
    print("Assistente Pessoal Completo")
    print(f"LLM: DeepSeek V3")
    print(f"{datetime.now(BRT):%d/%m/%Y %H:%M:%S}")
    print("=" * 50)
    print(f"[Roberto]  {WS_ROBERTO}")
    print(f"[Curioso]  {WS_CURIOSO}")
    print(f"[Marley]   {WS_MARLEY}")
    print(f"[Data]     {DATA_DIR}")
    print(f"[Gmail]    {'OK' if GMAIL_EMAIL else 'nao configurado'}")
    print(f"[Corp]     {'OK' if CORP_EMAIL else 'nao configurado'}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    cmds = [
        ("start", cmd_start), ("roberto", cmd_roberto), ("curioso", cmd_curioso),
        ("marley", cmd_marley), ("team", cmd_team),
        ("noticias", cmd_noticias), ("email", cmd_email), ("reddit", cmd_reddit),
        ("linkedin", cmd_linkedin), ("briefing", cmd_briefing),
        ("diario", cmd_diario), ("foco", cmd_foco), ("pausa", cmd_pausa),
        ("tarefa", cmd_tarefa), ("tarefas", cmd_tarefas), ("feito", cmd_feito),
        ("meta", cmd_meta), ("metas", cmd_metas), ("review", cmd_review),
        ("treino", cmd_treino), ("humor", cmd_humor),
        ("dash", cmd_dash), ("lembretes", cmd_lembretes),
        ("status", cmd_status), ("workspace", cmd_workspace), ("limpar", cmd_limpar),
    ]
    for cmd, fn in cmds:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_error_handler(error_handler)
    setup_saved_reminders(app)

    print(f"\n{len(cmds)} comandos registrados.")
    print("Bot pronto. Aguardando Telegram...\n")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
