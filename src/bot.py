# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v6.0
Roberto (Engenheiro) | Curioso (Pesquisador) | Marley (Criativo)
LLM: DeepSeek V3 via OpenAI-compatible API (NO CrewAI)
Tools are called DIRECTLY by Python - guaranteed execution.
Deploy: Render.com Background Worker
"""

import os
import re
import json
import subprocess
import logging
import warnings
from datetime import datetime
from io import BytesIO
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")
logging.getLogger("httpx").setLevel(logging.WARNING)

import requests as http_requests
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# CONFIG
# ============================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

BASE_DIR = Path(__file__).resolve().parent.parent
WS_ROBERTO = BASE_DIR / "workspace" / "roberto"
WS_CURIOSO = BASE_DIR / "workspace" / "curioso"
WS_MARLEY = BASE_DIR / "workspace" / "marley"

for d in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY):
    d.mkdir(parents=True, exist_ok=True)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)


# ============================================================
# LLM HELPER
# ============================================================

def chat(system_prompt, user_message, max_tokens=4000):
    """Simple chat completion with DeepSeek V3."""
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
    """Chat with function calling loop for Roberto."""
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

        # If no tool calls, return the text response
        if not msg.tool_calls:
            return msg.content.strip() if msg.content else "(sem resposta)"

        # Execute each tool call
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

    return messages[-1].get("content", "(max iteracoes atingido)")


# ============================================================
# TOOL IMPLEMENTATIONS
# ============================================================

def web_search(query, max_results=5):
    """Search the web via DuckDuckGo."""
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
    """Fetch and extract text from a URL."""
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
    """Generate image via Pollinations API. Returns (url, local_path, size) or error string."""
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
        # Fallback URL
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
        return f"ERRO: HTTP {resp.status_code} (primario) e HTTP {resp2.status_code} (fallback)"
    except Exception as e:
        return f"ERRO: {e}"


# ============================================================
# ROBERTO TOOLS (function calling)
# ============================================================

ROBERTO_TOOLS_DEF = [
    {
        "type": "function",
        "function": {
            "name": "criar_arquivo",
            "description": "Cria ou sobrescreve um arquivo no workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nome do arquivo (ex: app.py)"},
                    "content": {"type": "string", "description": "Conteudo completo do arquivo"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "executar_python",
            "description": "Executa codigo Python e retorna o resultado (stdout + stderr)",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Codigo Python completo"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "executar_bash",
            "description": "Executa comando shell (pip install, ls, cat, etc)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando bash"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ler_arquivo",
            "description": "Le conteudo de um arquivo existente no workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nome do arquivo"},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_workspace",
            "description": "Lista todos os arquivos no workspace",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def roberto_tool_executor(fn_name, fn_args):
    """Execute Roberto's tools."""
    if fn_name == "criar_arquivo":
        fn = fn_args.get("filename", "output.py")
        ct = fn_args.get("content", "")
        try:
            p = WS_ROBERTO / fn
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ct, encoding="utf-8")
            return f"OK arquivo criado: {fn} ({len(ct)} bytes)"
        except Exception as e:
            return f"ERRO: {e}"

    elif fn_name == "executar_python":
        code = fn_args.get("code", "")
        try:
            tmp = WS_ROBERTO / "_run.py"
            tmp.write_text(code, encoding="utf-8")
            r = subprocess.run(
                ["python3", str(tmp)], capture_output=True,
                text=True, timeout=30, cwd=str(WS_ROBERTO)
            )
            out = (r.stdout + "\n" + r.stderr).strip()
            return (out or "OK executado sem output")[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO: timeout 30s"
        except Exception as e:
            return f"ERRO: {e}"

    elif fn_name == "executar_bash":
        cmd = fn_args.get("command", "")
        if any(x in cmd for x in ["rm -rf /", "mkfs", ":(){"]):
            return "ERRO: bloqueado"
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=30, cwd=str(WS_ROBERTO)
            )
            return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
        except Exception as e:
            return f"ERRO: {e}"

    elif fn_name == "ler_arquivo":
        fn = fn_args.get("filename", "")
        try:
            p = WS_ROBERTO / fn
            if not p.exists():
                return f"ERRO: nao encontrado: {fn}"
            return p.read_text(encoding="utf-8")[:4000]
        except Exception as e:
            return f"ERRO: {e}"

    elif fn_name == "listar_workspace":
        fs = [f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")]
        if not fs:
            return "Workspace vazio"
        return "\n".join(str(f.relative_to(WS_ROBERTO)) for f in fs[:30])

    return f"ERRO: ferramenta desconhecida: {fn_name}"


# ============================================================
# TELEGRAM HELPERS
# ============================================================

def split_msg(text, max_len=4000):
    text = str(text).strip()
    if not text:
        return ["(sem resposta)"]
    if len(text) <= max_len:
        return [text]
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
    """Send image to Telegram chat."""
    # Try local file
    if local_path:
        try:
            if os.path.exists(local_path) and os.path.getsize(local_path) > 500:
                with open(local_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Imagem por Marley")
                return True
        except Exception:
            pass

    # Try URL
    if url:
        try:
            resp = http_requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 500:
                await update.message.reply_photo(
                    photo=BytesIO(resp.content), caption="Imagem por Marley"
                )
                return True
        except Exception:
            pass
        await update.message.reply_text(f"Imagem gerada:\n{url}")
        return True

    return False


# ============================================================
# BOT COMMANDS
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "=== IRONCORE AGENTS v6.0 ===\n"
        "LLM: DeepSeek V3\n\n"
        "[ROBERTO] Engenheiro de Software\n"
        "  Cria projetos completos com codigo real.\n"
        "  /roberto [tarefa]\n\n"
        "[CURIOSO] Pesquisador & Analista\n"
        "  Pesquisa na web real com fontes.\n"
        "  /curioso [pergunta]\n\n"
        "[MARLEY] Artista IA\n"
        "  Gera imagens reais com IA.\n"
        "  /marley [descricao]\n\n"
        "[TEAM] 3 agentes juntos\n"
        "  /team [projeto]\n\n"
        "Outros: /status  /workspace  /limpar"
    )


async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Curioso: ALWAYS searches the web first, then summarizes."""
    if not context.args:
        await update.message.reply_text("/curioso [pergunta]")
        return

    pergunta = " ".join(context.args)
    await update.message.reply_text(f"[Curioso] {pergunta}\nBuscando na web...")

    # Extract search keywords using DeepSeek
    keywords = chat(
        system_prompt=(
            "Extract 2-5 search keywords from the user query. "
            "Return ONLY the keywords separated by spaces, nothing else. "
            "Remove filler words like 'me fale sobre', 'o que e', etc. "
            "Example: 'me fale sobre inteligencia artificial' -> 'inteligencia artificial'"
        ),
        user_message=pergunta,
        max_tokens=50,
    )
    search_query = keywords if not keywords.startswith("[ERRO") else pergunta
    print(f"[CURIOSO] Query: '{pergunta}' -> Keywords: '{search_query}'")

    # STEP 1: Search the web (GUARANTEED - Python calls it directly)
    results = web_search(search_query)

    # Format results for the LLM
    search_text = ""
    for i, r in enumerate(results, 1):
        if "erro" in r:
            search_text += f"\n{r['erro']}"
        else:
            search_text += (
                f"\n--- Resultado {i} ---\n"
                f"Titulo: {r['titulo']}\n"
                f"Resumo: {r['resumo']}\n"
                f"Link: {r['link']}\n"
            )

    # STEP 2: Ask DeepSeek to summarize the REAL search results
    summary = chat(
        system_prompt=(
            "Voce e Curioso, analista de pesquisa. "
            "Responda a pergunta do usuario SOMENTE com base nos resultados de busca abaixo. "
            "Cite as fontes com links. "
            "Se os resultados nao responderem a pergunta, diga isso claramente. "
            "NUNCA invente informacoes que nao estejam nos resultados."
        ),
        user_message=(
            f"PERGUNTA: {pergunta}\n\n"
            f"RESULTADOS DA BUSCA WEB:\n{search_text}\n\n"
            f"Responda baseado SOMENTE nesses resultados. Cite fontes."
        ),
    )

    await send_long(update, f"[Curioso]\n\n{summary}")


async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marley: ALWAYS generates real images."""
    if not context.args:
        await update.message.reply_text("/marley [descricao]")
        return

    pedido = " ".join(context.args)
    await update.message.reply_text(f"[Marley] {pedido}\nGerando imagem...")

    # STEP 1: Ask DeepSeek to create an optimized English prompt
    prompt_en = chat(
        system_prompt=(
            "You are an AI image prompt engineer. "
            "Create a detailed image generation prompt in ENGLISH (50-100 words). "
            "Include: subject, art style, lighting, colors, composition, mood, quality keywords. "
            "Add 'highly detailed, professional quality, 8k' at the end. "
            "Return ONLY the prompt text, nothing else."
        ),
        user_message=f"Create image prompt for: {pedido}",
        max_tokens=300,
    )

    if prompt_en.startswith("[ERRO"):
        await update.message.reply_text(f"[Marley] Erro ao criar prompt: {prompt_en}")
        return

    print(f"[MARLEY] Prompt: {prompt_en[:100]}...")

    # STEP 2: Generate the image (GUARANTEED - Python calls Pollinations directly)
    result = generate_image(prompt_en)

    if isinstance(result, tuple):
        url, local_path, size = result
        sent = await send_image(update, url=url, local_path=local_path)
        if sent:
            await update.message.reply_text(
                f"[Marley]\n\nImagem gerada com sucesso ({size:,} bytes).\n"
                f"Prompt: {prompt_en[:200]}"
            )
        else:
            await update.message.reply_text(f"[Marley] Imagem gerada mas falha no envio.\nLink: {url}")
    else:
        await update.message.reply_text(f"[Marley] {result}")


async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roberto: Creates code using function calling with DeepSeek."""
    if not context.args:
        await update.message.reply_text("/roberto [tarefa]")
        return

    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Roberto] {tarefa}\nTrabalhando...")

    result = chat_with_tools(
        system_prompt=(
            "Voce e Roberto, engenheiro de software senior. "
            "Voce DEVE usar as ferramentas disponiveis para completar a tarefa. "
            "Processo: 1) Crie os arquivos com criar_arquivo, "
            "2) Teste com executar_python, 3) Corrija erros, 4) Entregue pronto. "
            "NUNCA de passo-a-passo. Voce CRIA os arquivos e EXECUTA o codigo. "
            "No final, liste os arquivos criados."
        ),
        user_message=f"TAREFA: {tarefa}",
        tools_def=ROBERTO_TOOLS_DEF,
        tool_executor=roberto_tool_executor,
        max_rounds=8,
    )

    await send_long(update, f"[Roberto]\n\n{result}")


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Team: All 3 agents work on the project."""
    if not context.args:
        await update.message.reply_text("/team [projeto]")
        return

    projeto = " ".join(context.args)
    await update.message.reply_text(f"[Team] {projeto}\nPesquisando, codando e criando visual...")

    # STEP 1: Curioso pesquisa
    results = web_search(projeto)
    search_text = ""
    for r in results:
        if "erro" not in r:
            search_text += f"- {r['titulo']}: {r['resumo'][:150]} ({r['link']})\n"

    pesquisa = chat(
        system_prompt="Voce e um pesquisador. Resuma os resultados da busca web de forma util para um projeto.",
        user_message=f"PROJETO: {projeto}\n\nRESULTADOS:\n{search_text}",
        max_tokens=1500,
    )

    # STEP 2: Roberto coda
    codigo = chat_with_tools(
        system_prompt=(
            "Voce e Roberto, engenheiro senior. "
            "Use as ferramentas para criar o codigo do projeto. "
            "Crie arquivos com criar_arquivo e teste com executar_python."
        ),
        user_message=f"PROJETO: {projeto}\nPESQUISA DE MERCADO:\n{pesquisa[:1000]}",
        tools_def=ROBERTO_TOOLS_DEF,
        tool_executor=roberto_tool_executor,
        max_rounds=6,
    )

    # STEP 3: Marley cria visual
    prompt_en = chat(
        system_prompt=(
            "You are an image prompt engineer. "
            "Create a prompt in English (50-80 words) for a visual related to this project. "
            "Return ONLY the prompt."
        ),
        user_message=f"Project: {projeto}",
        max_tokens=200,
    )

    img_result = generate_image(prompt_en)
    if isinstance(img_result, tuple):
        url, lp, sz = img_result
        await send_image(update, url=url, local_path=lp)

    # Send combined results
    full_result = (
        f"=== PESQUISA (Curioso) ===\n{pesquisa}\n\n"
        f"=== CODIGO (Roberto) ===\n{codigo}\n\n"
        f"=== VISUAL (Marley) ===\nImagem gerada."
    )
    await send_long(update, f"[Team]\n\n{full_result}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = len([f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")])
    cc = len([f for f in WS_CURIOSO.rglob("*") if f.is_file()])
    mc = len([f for f in WS_MARLEY.rglob("*") if f.is_file()])
    await update.message.reply_text(
        f"=== IRONCORE AGENTS v6.0 ===\n"
        f"LLM: DeepSeek V3 (direto, sem CrewAI)\n"
        f"{datetime.now():%d/%m/%Y %H:%M}\n\n"
        f"[Roberto] ONLINE - {rc} arquivo(s)\n"
        f"[Curioso] ONLINE - {cc} arquivo(s)\n"
        f"[Marley] ONLINE - {mc} arquivo(s)\n\n"
        f"Operacional."
    )


async def cmd_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "=== WORKSPACES ===\n\n"
    for nm, ws in [("Roberto", WS_ROBERTO), ("Curioso", WS_CURIOSO), ("Marley", WS_MARLEY)]:
        fs = [f for f in ws.rglob("*") if f.is_file() and not f.name.startswith("_")]
        msg += f"--- {nm} ---\n"
        for f in fs[:10]:
            msg += f"  {f.relative_to(ws)} ({f.stat().st_size:,}b)\n"
        if not fs:
            msg += "  (vazio)\n"
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
    print("IRONCORE AGENTS v6.0")
    print("LLM: DeepSeek V3 (direto, sem CrewAI)")
    print(f"{datetime.now():%d/%m/%Y %H:%M:%S}")
    print("=" * 50)
    print(f"\n[Roberto]  {WS_ROBERTO}")
    print(f"[Curioso]  {WS_CURIOSO}")
    print(f"[Marley]   {WS_MARLEY}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    for cmd, fn in [
        ("start", cmd_start), ("roberto", cmd_roberto),
        ("curioso", cmd_curioso), ("marley", cmd_marley),
        ("team", cmd_team), ("status", cmd_status),
        ("workspace", cmd_workspace), ("limpar", cmd_limpar),
    ]:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_error_handler(error_handler)

    print("\nBot pronto. Aguardando Telegram...\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
