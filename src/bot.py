# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v7.0
Roberto (Engenheiro) | Curioso (Pesquisador) | Marley (Criativo)
+ Modulo Vida: Journaling, Pomodoro, Tasks, Metas, Treino, Humor
LLM: DeepSeek V3 via OpenAI-compatible API
Deploy: Render.com Background Worker
"""

import os
import re
import json
import subprocess
import logging
import warnings
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")
logging.getLogger("httpx").setLevel(logging.WARNING)

import requests as http_requests
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackContext
)

# ============================================================
# CONFIG
# ============================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

BRT = timezone(timedelta(hours=-3))

BASE_DIR = Path(__file__).resolve().parent.parent
WS_ROBERTO = BASE_DIR / "workspace" / "roberto"
WS_CURIOSO = BASE_DIR / "workspace" / "curioso"
WS_MARLEY = BASE_DIR / "workspace" / "marley"
DATA_DIR = BASE_DIR / "data"

for d in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

MAX_RETRIES = 3
RETRY_DELAY = 10


# ============================================================
# STORAGE (JSON)
# ============================================================

def load_data(name):
    """Load JSON data file."""
    f = DATA_DIR / f"{name}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_data(name, data):
    """Save JSON data file."""
    f = DATA_DIR / f"{name}.json"
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def today_str():
    return datetime.now(BRT).strftime("%Y-%m-%d")


def now_str():
    return datetime.now(BRT).strftime("%Y-%m-%d %H:%M")


def week_key():
    d = datetime.now(BRT)
    start = d - timedelta(days=d.weekday())
    return start.strftime("%Y-W%W")


# ============================================================
# LLM HELPERS
# ============================================================

def chat(system_prompt, user_message, max_tokens=4000):
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERRO LLM] {e}"


def chat_with_tools(system_prompt, user_message, tools_def, tool_executor, max_rounds=6):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    for _ in range(max_rounds):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=tools_def,
                tool_choice="auto",
                max_tokens=4000,
                temperature=0.3,
            )
        except Exception as e:
            return f"[ERRO LLM] {e}"
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content.strip() if msg.content else "(sem resposta)"
        messages.append(msg)
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}
            result = tool_executor(fn_name, fn_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)[:3000],
            })
    return messages[-1].get("content", "(max iteracoes)")


# ============================================================
# TOOL IMPLEMENTATIONS (Agents)
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
                results.append({
                    "titulo": r["title"],
                    "resumo": r["body"][:300],
                    "link": r["href"],
                })
        return results if results else [{"erro": f"Nenhum resultado para: {query}"}]
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
                return f"ERRO: imagem muito pequena ({len(data)} bytes)"
            nm = f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
            fp = WS_MARLEY / nm
            fp.write_bytes(data)
            print(f"[MARLEY] Salvo: {fp} ({len(data)} bytes)")
            return (url, str(fp), len(data))
        url2 = f"https://pollinations.ai/p/{encoded}"
        print(f"[MARLEY] Fallback: {url2[:100]}...")
        resp2 = http_requests.get(url2, timeout=120, stream=True)
        print(f"[MARLEY] Fallback HTTP {resp2.status_code}")
        if resp2.status_code == 200:
            data = b"".join(resp2.iter_content(8192))
            if len(data) < 500:
                return f"ERRO: imagem fallback muito pequena"
            nm = f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
            fp = WS_MARLEY / nm
            fp.write_bytes(data)
            return (url2, str(fp), len(data))
        return f"ERRO: HTTP {resp.status_code} / fallback {resp2.status_code}"
    except Exception as e:
        return f"ERRO: {e}"


# ============================================================
# ROBERTO TOOLS
# ============================================================

ROBERTO_TOOLS_DEF = [
    {"type": "function", "function": {
        "name": "criar_arquivo",
        "description": "Cria ou sobrescreve arquivo no workspace",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string", "description": "Nome do arquivo"},
            "content": {"type": "string", "description": "Conteudo do arquivo"},
        }, "required": ["filename", "content"]},
    }},
    {"type": "function", "function": {
        "name": "executar_python",
        "description": "Executa codigo Python e retorna resultado",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Codigo Python"},
        }, "required": ["code"]},
    }},
    {"type": "function", "function": {
        "name": "executar_bash",
        "description": "Executa comando shell",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "Comando bash"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "ler_arquivo",
        "description": "Le conteudo de arquivo do workspace",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string", "description": "Nome do arquivo"},
        }, "required": ["filename"]},
    }},
    {"type": "function", "function": {
        "name": "listar_workspace",
        "description": "Lista arquivos no workspace",
        "parameters": {"type": "object", "properties": {}},
    }},
]


def roberto_tool_executor(fn_name, fn_args):
    if fn_name == "criar_arquivo":
        fn = fn_args.get("filename", "output.py")
        ct = fn_args.get("content", "")
        try:
            p = WS_ROBERTO / fn
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ct, encoding="utf-8")
            return f"OK: {fn} ({len(ct)} bytes)"
        except Exception as e:
            return f"ERRO: {e}"
    elif fn_name == "executar_python":
        code = fn_args.get("code", "")
        try:
            tmp = WS_ROBERTO / "_run.py"
            tmp.write_text(code, encoding="utf-8")
            r = subprocess.run(
                ["python3", str(tmp)], capture_output=True,
                text=True, timeout=30, cwd=str(WS_ROBERTO))
            return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO: timeout 30s"
        except Exception as e:
            return f"ERRO: {e}"
    elif fn_name == "executar_bash":
        cmd = fn_args.get("command", "")
        if any(x in cmd for x in ["rm -rf /", "mkfs", ":(){"]):
            return "ERRO: bloqueado"
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                text=True, timeout=30, cwd=str(WS_ROBERTO))
            return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
        except Exception as e:
            return f"ERRO: {e}"
    elif fn_name == "ler_arquivo":
        fn = fn_args.get("filename", "")
        try:
            p = WS_ROBERTO / fn
            if not p.exists(): return f"ERRO: nao encontrado: {fn}"
            return p.read_text(encoding="utf-8")[:4000]
        except Exception as e:
            return f"ERRO: {e}"
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
                for i in range(0, len(par), max_len):
                    chunks.append(par[i:i+max_len])
                cur = ""
            else:
                cur = par + "\n\n"
    if cur.strip(): chunks.append(cur.strip())
    return chunks if chunks else [text[:max_len]]


async def send_long(update, text):
    parts = split_msg(text)
    for i, chunk in enumerate(parts):
        try:
            pref = f"(parte {i+1}/{len(parts)})\n\n" if len(parts) > 1 and i > 0 else ""
            await update.message.reply_text(pref + chunk)
        except Exception:
            pass


async def send_image(update, url=None, local_path=None):
    if local_path:
        try:
            if os.path.exists(local_path) and os.path.getsize(local_path) > 500:
                with open(local_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Imagem por Marley")
                return True
        except Exception:
            pass
    if url:
        try:
            resp = http_requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 500:
                await update.message.reply_photo(photo=BytesIO(resp.content), caption="Imagem por Marley")
                return True
        except Exception:
            pass
        await update.message.reply_text(f"Imagem:\n{url}")
        return True
    return False


# ============================================================
# AGENT COMMANDS (Roberto, Curioso, Marley, Team)
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "=== IRONCORE AGENTS v7.0 ===\n"
        "LLM: DeepSeek V3\n\n"
        "--- AGENTES ---\n"
        "/roberto [tarefa] - Engenheiro\n"
        "/curioso [pergunta] - Pesquisador\n"
        "/marley [descricao] - Artista IA\n"
        "/team [projeto] - 3 agentes\n\n"
        "--- PRODUTIVIDADE ---\n"
        "/diario [texto] - Journaling\n"
        "/foco [min] - Pomodoro\n"
        "/tarefa [texto] - Nova tarefa\n"
        "/tarefas - Ver pendentes\n"
        "/feito [n] - Completar tarefa\n"
        "/meta [texto] - Meta semanal\n"
        "/metas - Ver metas\n"
        "/review - Review semanal IA\n\n"
        "--- SAUDE ---\n"
        "/treino [tipo] - Registrar exercicio\n"
        "/humor [1-5] [nota] - Humor/energia\n\n"
        "--- GERAL ---\n"
        "/dash - Dashboard do dia\n"
        "/status - Status do sistema\n"
        "/lembretes - Configurar lembretes\n"
        "/workspace - Ver arquivos\n"
        "/limpar - Limpar workspaces"
    )


async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/roberto [tarefa]"); return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Roberto] {tarefa}\nTrabalhando...")
    result = chat_with_tools(
        system_prompt=(
            "Voce e Roberto, engenheiro senior. "
            "Use as ferramentas para criar arquivos e testar codigo. "
            "NUNCA de passo-a-passo. Voce CRIA e EXECUTA."
        ),
        user_message=f"TAREFA: {tarefa}",
        tools_def=ROBERTO_TOOLS_DEF,
        tool_executor=roberto_tool_executor,
        max_rounds=8,
    )
    await send_long(update, f"[Roberto]\n\n{result}")


async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/curioso [pergunta]"); return
    pergunta = " ".join(context.args)
    await update.message.reply_text(f"[Curioso] {pergunta}\nBuscando...")
    keywords = chat(
        system_prompt="Extract 2-5 search keywords. Return ONLY keywords, nothing else.",
        user_message=pergunta, max_tokens=50)
    sq = keywords if not keywords.startswith("[ERRO") else pergunta
    print(f"[CURIOSO] '{pergunta}' -> '{sq}'")
    results = web_search(sq)
    stxt = ""
    for i, r in enumerate(results, 1):
        if "erro" in r: stxt += f"\n{r['erro']}"
        else: stxt += f"\n--- {i} ---\nTitulo: {r['titulo']}\nResumo: {r['resumo']}\nLink: {r['link']}\n"
    summary = chat(
        system_prompt="Responda SOMENTE com dados da busca. Cite fontes. NUNCA invente.",
        user_message=f"PERGUNTA: {pergunta}\n\nRESULTADOS:\n{stxt}\n\nResponda com fontes.")
    await send_long(update, f"[Curioso]\n\n{summary}")


async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/marley [descricao]"); return
    pedido = " ".join(context.args)
    await update.message.reply_text(f"[Marley] {pedido}\nGerando...")
    prompt_en = chat(
        system_prompt=(
            "Create a detailed image prompt in ENGLISH (50-100 words). "
            "Include subject, style, lighting, colors, mood. "
            "Add 'highly detailed, 8k' at end. Return ONLY the prompt."
        ),
        user_message=f"Create image prompt for: {pedido}", max_tokens=300)
    if prompt_en.startswith("[ERRO"):
        await update.message.reply_text(f"[Marley] {prompt_en}"); return
    print(f"[MARLEY] Prompt: {prompt_en[:100]}...")
    result = generate_image(prompt_en)
    if isinstance(result, tuple):
        url, lp, sz = result
        sent = await send_image(update, url=url, local_path=lp)
        if sent:
            await update.message.reply_text(f"[Marley] Imagem gerada ({sz:,} bytes)")
    else:
        await update.message.reply_text(f"[Marley] {result}")


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/team [projeto]"); return
    projeto = " ".join(context.args)
    await update.message.reply_text(f"[Team] {projeto}\n3 agentes...")
    results = web_search(projeto)
    stxt = "".join(f"- {r['titulo']}: {r['resumo'][:150]}\n" for r in results if "erro" not in r)
    pesquisa = chat("Resuma os resultados para um projeto.", f"PROJETO: {projeto}\n{stxt}", 1500)
    codigo = chat_with_tools(
        "Voce e Roberto. Crie codigo com criar_arquivo e teste.",
        f"PROJETO: {projeto}\nPESQUISA:\n{pesquisa[:1000]}",
        ROBERTO_TOOLS_DEF, roberto_tool_executor, 6)
    prompt_en = chat("Create image prompt in English (50 words). Return ONLY prompt.",
        f"Project: {projeto}", 200)
    img = generate_image(prompt_en)
    if isinstance(img, tuple):
        await send_image(update, url=img[0], local_path=img[1])
    await send_long(update, f"[Team]\n\n=== PESQUISA ===\n{pesquisa}\n\n=== CODIGO ===\n{codigo}")


# ============================================================
# JOURNALING
# ============================================================

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("diario")
    hoje = today_str()

    if not context.args:
        # Show today's entries
        entries = data.get(hoje, [])
        if not entries:
            await update.message.reply_text(
                f"Diario {hoje}: nenhuma entrada.\n\n"
                "Use: /diario [seu texto]")
            return
        msg = f"=== Diario {hoje} ===\n\n"
        for i, e in enumerate(entries, 1):
            msg += f"{i}. [{e['hora']}] {e['texto']}\n\n"
        await update.message.reply_text(msg)
        return

    texto = " ".join(context.args)
    if hoje not in data:
        data[hoje] = []
    data[hoje].append({
        "hora": datetime.now(BRT).strftime("%H:%M"),
        "texto": texto,
    })
    save_data("diario", data)
    n = len(data[hoje])
    await update.message.reply_text(
        f"Diario registrado ({n}a entrada de hoje).\n\n\"{texto[:100]}\"")


# ============================================================
# POMODORO
# ============================================================

async def pomodoro_done(context: CallbackContext):
    """Callback when pomodoro timer ends."""
    chat_id = context.job.chat_id
    task_name = context.job.data or "Foco"

    # Log completed pomodoro
    data = load_data("pomodoros")
    hoje = today_str()
    if hoje not in data:
        data[hoje] = []
    data[hoje].append({
        "hora": datetime.now(BRT).strftime("%H:%M"),
        "tarefa": task_name,
        "minutos": context.job.name.split("_")[-1] if "_" in context.job.name else "25",
    })
    save_data("pomodoros", data)

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"POMODORO COMPLETO!\n\n"
            f"Tarefa: {task_name}\n"
            f"Hora de pausar 5 minutos.\n\n"
            f"Pomodoros hoje: {len(data[hoje])}"
        )
    )


async def cmd_foco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    minutos = 25
    tarefa = "Foco geral"

    if args:
        # Check if first arg is a number
        try:
            minutos = int(args[0])
            tarefa = " ".join(args[1:]) or "Foco geral"
        except ValueError:
            tarefa = " ".join(args)

    if minutos < 1 or minutos > 120:
        await update.message.reply_text("Tempo deve ser entre 1 e 120 minutos.")
        return

    # Remove existing pomodoro jobs for this chat
    jobs = context.job_queue.get_jobs_by_name(f"pomo_{update.effective_chat.id}")
    for j in jobs:
        j.schedule_removal()

    context.job_queue.run_once(
        pomodoro_done,
        when=timedelta(minutes=minutos),
        chat_id=update.effective_chat.id,
        name=f"pomo_{update.effective_chat.id}_{minutos}",
        data=tarefa,
    )

    await update.message.reply_text(
        f"POMODORO INICIADO\n\n"
        f"Tarefa: {tarefa}\n"
        f"Duracao: {minutos} minutos\n"
        f"Termina as: {(datetime.now(BRT) + timedelta(minutes=minutos)).strftime('%H:%M')}\n\n"
        f"Foco total! Vou te avisar quando acabar."
    )


async def cmd_pausa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name(f"pomo_{update.effective_chat.id}")
    if not jobs:
        # Try broader search
        all_jobs = [j for j in context.job_queue.jobs()
                    if j.name.startswith(f"pomo_{update.effective_chat.id}")]
        if not all_jobs:
            await update.message.reply_text("Nenhum pomodoro ativo.")
            return
        for j in all_jobs:
            j.schedule_removal()
    else:
        for j in jobs:
            j.schedule_removal()
    await update.message.reply_text("Pomodoro cancelado.")


# ============================================================
# TASKS
# ============================================================

async def cmd_tarefa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /tarefa [descricao da tarefa]"); return

    data = load_data("tarefas")
    if "items" not in data:
        data["items"] = []
        data["next_id"] = 1

    texto = " ".join(context.args)
    tid = data["next_id"]
    data["items"].append({
        "id": tid,
        "texto": texto,
        "criada": now_str(),
        "feita": False,
        "feita_em": None,
    })
    data["next_id"] = tid + 1
    save_data("tarefas", data)
    await update.message.reply_text(f"Tarefa #{tid} criada:\n\"{texto}\"")


async def cmd_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("tarefas")
    items = data.get("items", [])
    pendentes = [t for t in items if not t["feita"]]
    feitas_hoje = [t for t in items if t["feita"] and t.get("feita_em", "").startswith(today_str())]

    if not pendentes and not feitas_hoje:
        await update.message.reply_text("Nenhuma tarefa.\nUse: /tarefa [texto]")
        return

    msg = "=== TAREFAS ===\n\n"
    if pendentes:
        msg += "PENDENTES:\n"
        for t in pendentes:
            msg += f"  #{t['id']} - {t['texto']}\n"
        msg += "\n"
    if feitas_hoje:
        msg += f"CONCLUIDAS HOJE ({len(feitas_hoje)}):\n"
        for t in feitas_hoje:
            msg += f"  #{t['id']} - {t['texto']}\n"

    msg += f"\nTotal: {len(pendentes)} pendente(s)"
    msg += "\nUse /feito [n] para completar"
    await update.message.reply_text(msg)


async def cmd_feito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /feito [numero]"); return

    try:
        tid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Use numero: /feito 1"); return

    data = load_data("tarefas")
    for t in data.get("items", []):
        if t["id"] == tid and not t["feita"]:
            t["feita"] = True
            t["feita_em"] = now_str()
            save_data("tarefas", data)
            pendentes = len([x for x in data["items"] if not x["feita"]])
            await update.message.reply_text(
                f"Tarefa #{tid} concluida!\n\"{t['texto']}\"\n\n"
                f"Restam {pendentes} pendente(s).")
            return

    await update.message.reply_text(f"Tarefa #{tid} nao encontrada ou ja concluida.")


# ============================================================
# WEEKLY GOALS
# ============================================================

async def cmd_meta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /meta [sua meta semanal]"); return

    data = load_data("metas")
    wk = week_key()
    if wk not in data:
        data[wk] = []

    texto = " ".join(context.args)
    data[wk].append({
        "texto": texto,
        "criada": now_str(),
        "concluida": False,
    })
    save_data("metas", data)
    await update.message.reply_text(
        f"Meta semanal adicionada ({len(data[wk])} metas esta semana):\n\"{texto}\"")


async def cmd_metas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("metas")
    wk = week_key()
    metas = data.get(wk, [])

    if not metas:
        await update.message.reply_text(
            f"Sem metas para semana {wk}.\nUse: /meta [texto]")
        return

    msg = f"=== METAS SEMANA {wk} ===\n\n"
    for i, m in enumerate(metas, 1):
        status = "OK" if m["concluida"] else "..."
        msg += f"  {i}. [{status}] {m['texto']}\n"

    done = sum(1 for m in metas if m["concluida"])
    msg += f"\nProgresso: {done}/{len(metas)}"
    await update.message.reply_text(msg)


# ============================================================
# EXERCISE TRACKING
# ============================================================

async def cmd_treino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("treinos")
    hoje = today_str()

    if not context.args:
        # Show recent workouts
        all_treinos = []
        for d, ts in sorted(data.items(), reverse=True)[:7]:
            for t in ts:
                all_treinos.append(f"  [{d} {t['hora']}] {t['tipo']}")
        if not all_treinos:
            await update.message.reply_text("Nenhum treino registrado.\nUse: /treino [tipo]")
            return
        await update.message.reply_text(
            f"=== TREINOS (ultimos 7 dias) ===\n\n" + "\n".join(all_treinos))
        return

    tipo = " ".join(context.args)
    if hoje not in data:
        data[hoje] = []
    data[hoje].append({
        "hora": datetime.now(BRT).strftime("%H:%M"),
        "tipo": tipo,
    })
    save_data("treinos", data)

    # Count this week
    week_count = 0
    for i in range(7):
        d = (datetime.now(BRT) - timedelta(days=i)).strftime("%Y-%m-%d")
        week_count += len(data.get(d, []))

    await update.message.reply_text(
        f"Treino registrado: {tipo}\n"
        f"Treinos esta semana: {week_count}")


# ============================================================
# MOOD/ENERGY TRACKING
# ============================================================

async def cmd_humor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data("humor")
    hoje = today_str()

    if not context.args:
        # Show recent moods
        entries = []
        for d in sorted(data.keys(), reverse=True)[:7]:
            for e in data[d]:
                emoji = ["", "1/5", "2/5", "3/5", "4/5", "5/5"][e["nivel"]]
                entries.append(f"  [{d} {e['hora']}] {emoji} {e['nivel']}/5 - {e.get('nota', '')}")
        if not entries:
            await update.message.reply_text(
                "Nenhum registro de humor.\n"
                "Use: /humor [1-5] [nota opcional]\n"
                "1=pessimo  3=neutro  5=otimo")
            return
        await update.message.reply_text(
            "=== HUMOR/ENERGIA ===\n\n" + "\n".join(entries))
        return

    try:
        nivel = int(context.args[0])
        if nivel < 1 or nivel > 5:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Use: /humor [1-5] [nota]\nExemplo: /humor 4 me sinto bem")
        return

    nota = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    if hoje not in data:
        data[hoje] = []
    data[hoje].append({
        "hora": datetime.now(BRT).strftime("%H:%M"),
        "nivel": nivel,
        "nota": nota,
    })
    save_data("humor", data)

    emoji = ["", "1/5", "2/5", "3/5", "4/5", "5/5"][nivel]
    await update.message.reply_text(f"Humor registrado: {emoji} {nivel}/5\n{nota}")


# ============================================================
# DASHBOARD
# ============================================================

async def cmd_dash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = today_str()
    agora = datetime.now(BRT).strftime("%H:%M")

    # Diario
    diario = load_data("diario")
    d_entries = diario.get(hoje, [])

    # Tarefas
    tarefas = load_data("tarefas")
    pendentes = [t for t in tarefas.get("items", []) if not t["feita"]]
    feitas_hoje = [t for t in tarefas.get("items", []) if t["feita"] and
                   t.get("feita_em", "").startswith(hoje)]

    # Pomodoros
    pomos = load_data("pomodoros")
    pomo_hoje = pomos.get(hoje, [])

    # Treinos
    treinos = load_data("treinos")
    treino_hoje = treinos.get(hoje, [])

    # Humor
    humor = load_data("humor")
    humor_hoje = humor.get(hoje, [])

    # Metas
    metas_data = load_data("metas")
    wk = week_key()
    metas = metas_data.get(wk, [])
    metas_done = sum(1 for m in metas if m["concluida"])

    # Build dashboard
    msg = (
        f"=== DASHBOARD {hoje} ({agora}) ===\n\n"
        f"DIARIO: {len(d_entries)} entrada(s)\n"
    )
    for e in d_entries[-3:]:
        msg += f"  [{e['hora']}] {e['texto'][:60]}\n"

    msg += (
        f"\nTAREFAS: {len(feitas_hoje)} feita(s) / {len(pendentes)} pendente(s)\n"
    )
    for t in pendentes[:5]:
        msg += f"  #{t['id']} {t['texto'][:50]}\n"

    msg += f"\nPOMODOROS: {len(pomo_hoje)} sessao(es) hoje\n"
    msg += f"TREINO: {len(treino_hoje)} sessao(es) hoje\n"

    if humor_hoje:
        last = humor_hoje[-1]
        emoji = ["", "1/5", "2/5", "3/5", "4/5", "5/5"][last["nivel"]]
        msg += f"HUMOR: {emoji} {last['nivel']}/5\n"
    else:
        msg += "HUMOR: nao registrado\n"

    msg += f"\nMETAS SEMANA: {metas_done}/{len(metas)}\n"
    for m in metas:
        s = "OK" if m["concluida"] else "..."
        msg += f"  [{s}] {m['texto'][:50]}\n"

    await update.message.reply_text(msg)


# ============================================================
# AI WEEKLY REVIEW
# ============================================================

async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("[Review] Analisando sua semana...")

    # Collect all data from past 7 days
    days = [(datetime.now(BRT) - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    diario = load_data("diario")
    tarefas = load_data("tarefas")
    pomos = load_data("pomodoros")
    treinos = load_data("treinos")
    humor = load_data("humor")
    metas_data = load_data("metas")

    # Build context
    ctx = "DADOS DA SEMANA:\n\n"

    ctx += "DIARIO:\n"
    for d in days:
        entries = diario.get(d, [])
        if entries:
            ctx += f"  {d}:\n"
            for e in entries:
                ctx += f"    [{e['hora']}] {e['texto'][:200]}\n"

    ctx += "\nTAREFAS CONCLUIDAS:\n"
    for t in tarefas.get("items", []):
        if t["feita"] and t.get("feita_em", "")[:10] in days:
            ctx += f"  {t['feita_em']}: {t['texto']}\n"

    ctx += f"\nTAREFAS PENDENTES: {len([t for t in tarefas.get('items', []) if not t['feita']])}\n"

    ctx += "\nPOMODOROS:\n"
    total_pomos = 0
    for d in days:
        ps = pomos.get(d, [])
        total_pomos += len(ps)
        if ps:
            ctx += f"  {d}: {len(ps)} sessoes\n"

    ctx += f"\nTREINOS:\n"
    total_treinos = 0
    for d in days:
        ts = treinos.get(d, [])
        total_treinos += len(ts)
        if ts:
            for t in ts:
                ctx += f"  {d}: {t['tipo']}\n"

    ctx += f"\nHUMOR:\n"
    for d in days:
        hs = humor.get(d, [])
        if hs:
            for h in hs:
                ctx += f"  {d} [{h['hora']}]: {h['nivel']}/5 {h.get('nota', '')}\n"

    wk = week_key()
    metas = metas_data.get(wk, [])
    ctx += f"\nMETAS SEMANA ({wk}):\n"
    for m in metas:
        s = "CONCLUIDA" if m["concluida"] else "PENDENTE"
        ctx += f"  [{s}] {m['texto']}\n"

    # Ask AI for review
    review = chat(
        system_prompt=(
            "Voce e um coach pessoal analisando a semana do usuario. "
            "Seja direto, motivador e pratico. Responda em portugues. "
            "Estruture assim:\n"
            "1. RESUMO DA SEMANA (2-3 frases)\n"
            "2. DESTAQUES POSITIVOS\n"
            "3. PONTOS DE ATENCAO\n"
            "4. SUGESTOES PARA PROXIMA SEMANA\n"
            "5. NOTA DA SEMANA (0-10)\n"
            "Se nao houver dados, incentive o usuario a comecar a registrar."
        ),
        user_message=ctx,
        max_tokens=2000,
    )

    await send_long(update, f"[Review Semanal]\n\n{review}")


# ============================================================
# REMINDERS
# ============================================================

async def send_reminder(context: CallbackContext):
    """Send scheduled reminder."""
    msg = context.job.data
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=msg,
    )


async def cmd_lembretes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure daily reminders."""
    data = load_data("lembretes")
    chat_id = update.effective_chat.id

    if not context.args:
        # Show current reminders
        rems = data.get("ativos", [])
        if not rems:
            await update.message.reply_text(
                "Nenhum lembrete ativo.\n\n"
                "Exemplos:\n"
                "/lembretes treino 07:00\n"
                "/lembretes diario 22:00\n"
                "/lembretes agua 09:00\n"
                "/lembretes limpar")
            return
        msg = "=== LEMBRETES ===\n\n"
        for i, r in enumerate(rems, 1):
            msg += f"  {i}. {r['tipo']} as {r['hora']}\n"
        msg += "\n/lembretes limpar - remove todos"
        await update.message.reply_text(msg)
        return

    if context.args[0] == "limpar":
        data["ativos"] = []
        save_data("lembretes", data)
        # Clear all reminder jobs
        for j in context.job_queue.jobs():
            if j.name.startswith("reminder_"):
                j.schedule_removal()
        await update.message.reply_text("Lembretes removidos.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Use: /lembretes [tipo] [HH:MM]"); return

    tipo = context.args[0]
    hora_str = context.args[1]
    try:
        h, m = map(int, hora_str.split(":"))
        if h < 0 or h > 23 or m < 0 or m > 59:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Hora invalida. Use HH:MM (ex: 07:30)"); return

    msgs = {
        "treino": "Hora do treino! Bora se exercitar hoje?",
        "diario": "Que tal registrar seu diario? Use /diario [texto]",
        "agua": "Beba agua! Hidratacao e fundamental.",
        "humor": "Como voce esta se sentindo? Use /humor [1-5]",
        "foco": "Hora de focar! Use /foco para iniciar um pomodoro.",
        "review": "Hora da review semanal! Use /review",
    }
    msg_text = msgs.get(tipo, f"Lembrete: {tipo}")

    if "ativos" not in data:
        data["ativos"] = []
    data["ativos"].append({"tipo": tipo, "hora": hora_str, "chat_id": chat_id})
    save_data("lembretes", data)

    # Schedule the reminder
    from datetime import time as dt_time
    context.job_queue.run_daily(
        send_reminder,
        time=dt_time(hour=h, minute=m, tzinfo=BRT),
        chat_id=chat_id,
        name=f"reminder_{tipo}_{hora_str}",
        data=msg_text,
    )

    await update.message.reply_text(f"Lembrete configurado: {tipo} as {hora_str} diariamente.")


def setup_saved_reminders(app):
    """Restore saved reminders on startup."""
    data = load_data("lembretes")
    from datetime import time as dt_time
    msgs = {
        "treino": "Hora do treino! Bora se exercitar hoje?",
        "diario": "Que tal registrar seu diario? Use /diario [texto]",
        "agua": "Beba agua! Hidratacao e fundamental.",
        "humor": "Como voce esta se sentindo? Use /humor [1-5]",
        "foco": "Hora de focar! Use /foco para iniciar um pomodoro.",
        "review": "Hora da review semanal! Use /review",
    }
    for r in data.get("ativos", []):
        try:
            h, m = map(int, r["hora"].split(":"))
            tipo = r["tipo"]
            chat_id = r["chat_id"]
            msg_text = msgs.get(tipo, f"Lembrete: {tipo}")
            app.job_queue.run_daily(
                send_reminder,
                time=dt_time(hour=h, minute=m, tzinfo=BRT),
                chat_id=chat_id,
                name=f"reminder_{tipo}_{r['hora']}",
                data=msg_text,
            )
            print(f"[LEMBRETE] Restaurado: {tipo} as {r['hora']}")
        except Exception as e:
            print(f"[LEMBRETE] Erro: {e}")


# ============================================================
# UTILITY COMMANDS
# ============================================================

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = len([f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")])
    cc = len([f for f in WS_CURIOSO.rglob("*") if f.is_file()])
    mc = len([f for f in WS_MARLEY.rglob("*") if f.is_file()])
    tarefas = load_data("tarefas")
    pend = len([t for t in tarefas.get("items", []) if not t["feita"]])
    await update.message.reply_text(
        f"=== IRONCORE AGENTS v7.0 ===\n"
        f"LLM: DeepSeek V3\n"
        f"{datetime.now(BRT):%d/%m/%Y %H:%M}\n\n"
        f"[Roberto] ONLINE - {rc} arquivo(s)\n"
        f"[Curioso] ONLINE - {cc} arquivo(s)\n"
        f"[Marley] ONLINE - {mc} arquivo(s)\n\n"
        f"Tarefas pendentes: {pend}\n"
        f"Operacional.")


async def cmd_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "=== WORKSPACES ===\n\n"
    for nm, ws in [("Roberto", WS_ROBERTO), ("Curioso", WS_CURIOSO), ("Marley", WS_MARLEY)]:
        fs = [f for f in ws.rglob("*") if f.is_file() and not f.name.startswith("_")]
        msg += f"--- {nm} ---\n"
        for f in fs[:10]:
            msg += f"  {f.relative_to(ws)} ({f.stat().st_size:,}b)\n"
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
# ERROR HANDLER + MAIN
# ============================================================

async def error_handler(update, context):
    err = str(context.error)
    if "Conflict" in err or "terminated by other" in err:
        return
    print(f"[TELEGRAM ERROR] {err}")


def main():
    print("=" * 50)
    print("IRONCORE AGENTS v7.0")
    print("LLM: DeepSeek V3 (direto, sem CrewAI)")
    print(f"{datetime.now(BRT):%d/%m/%Y %H:%M:%S}")
    print("=" * 50)
    print(f"\n[Roberto]  {WS_ROBERTO}")
    print(f"[Curioso]  {WS_CURIOSO}")
    print(f"[Marley]   {WS_MARLEY}")
    print(f"[Data]     {DATA_DIR}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Agent commands
    for cmd, fn in [
        ("start", cmd_start), ("roberto", cmd_roberto),
        ("curioso", cmd_curioso), ("marley", cmd_marley),
        ("team", cmd_team),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    # Life commands
    for cmd, fn in [
        ("diario", cmd_diario), ("foco", cmd_foco), ("pausa", cmd_pausa),
        ("tarefa", cmd_tarefa), ("tarefas", cmd_tarefas), ("feito", cmd_feito),
        ("meta", cmd_meta), ("metas", cmd_metas), ("review", cmd_review),
        ("treino", cmd_treino), ("humor", cmd_humor),
        ("dash", cmd_dash), ("lembretes", cmd_lembretes),
        ("status", cmd_status), ("workspace", cmd_workspace), ("limpar", cmd_limpar),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_error_handler(error_handler)

    # Restore saved reminders
    setup_saved_reminders(app)

    print("\nBot pronto. Aguardando Telegram...\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
