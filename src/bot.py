# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v5.0
Roberto (Engenheiro) | Curioso (Pesquisador) | Marley (Criativo)
LLM: DeepSeek V3 via DeepSeek API
Deploy: Render.com Background Worker
"""

import os
import re
import sys
import time
import logging
import subprocess
import warnings
from datetime import datetime
from io import BytesIO
from pathlib import Path

# ==== SUPPRESS ALL WARNINGS BEFORE IMPORTS ====
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["ANONYMIZED_TELEMETRY"] = "false"
warnings.filterwarnings("ignore")
logging.getLogger("litellm").setLevel(logging.CRITICAL)
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("crewai").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.WARNING)

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool

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

llm = LLM(
    model="deepseek/deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    temperature=0.3,
)

MAX_RETRIES = 3
RETRY_DELAY = 10


# ============================================================
# RETRY WRAPPER
# ============================================================

def run_crew_with_retry(crew):
    for attempt in range(MAX_RETRIES):
        try:
            result = crew.kickoff()
            return str(result)
        except Exception as e:
            err = str(e).lower()
            if "rate_limit" in err or "429" in err or "rate limit" in err:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    print(f"[RETRY] Rate limit. Waiting {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    continue
            raise e
    return "Erro: limite de tentativas excedido"


# ============================================================
# TOOLS - ROBERTO
# ============================================================

class ToolCriarArquivo(BaseTool):
    name: str = "criar_arquivo"
    description: str = "Cria arquivo no workspace. Params: filename (str), content (str)"
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", kw.get("name", "output.py"))
        ct = content or kw.get("code", kw.get("file_content", kw.get("text", "")))
        try:
            p = WS_ROBERTO / fn
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ct, encoding="utf-8")
            return f"OK arquivo criado: {fn} ({len(ct)} bytes)"
        except Exception as e:
            return f"ERRO: {e}"


class ToolExecutarPython(BaseTool):
    name: str = "executar_python"
    description: str = "Executa codigo Python e retorna stdout+stderr. Param: code (str)"
    def _run(self, code: str = "", **kw) -> str:
        c = code or kw.get("script", kw.get("python_code", ""))
        try:
            f = WS_ROBERTO / "_run.py"
            f.write_text(c, encoding="utf-8")
            r = subprocess.run(
                ["python3", str(f)], capture_output=True,
                text=True, timeout=30, cwd=str(WS_ROBERTO)
            )
            o = (r.stdout + "\n" + r.stderr).strip()
            return (o or "OK executado sem output")[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO: timeout 30s"
        except Exception as e:
            return f"ERRO: {e}"


class ToolBash(BaseTool):
    name: str = "executar_bash"
    description: str = "Executa comando shell no workspace. Param: command (str)"
    def _run(self, command: str = "", **kw) -> str:
        cmd = command or kw.get("cmd", "")
        if any(x in cmd for x in ["rm -rf /", "mkfs", ":(){"]):
            return "ERRO: comando bloqueado"
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=30, cwd=str(WS_ROBERTO)
            )
            return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO: timeout 30s"
        except Exception as e:
            return f"ERRO: {e}"


class ToolLerArquivo(BaseTool):
    name: str = "ler_arquivo"
    description: str = "Le conteudo de arquivo do workspace. Param: filename (str)"
    def _run(self, filename: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", kw.get("path", ""))
        try:
            p = WS_ROBERTO / fn
            if not p.exists():
                return f"ERRO: nao encontrado: {fn}"
            return p.read_text(encoding="utf-8")[:4000]
        except Exception as e:
            return f"ERRO: {e}"


class ToolListarWS(BaseTool):
    name: str = "listar_workspace"
    description: str = "Lista todos os arquivos no workspace do Roberto"
    def _run(self, **kw) -> str:
        fs = [f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")]
        if not fs:
            return "Workspace vazio"
        return "Arquivos:\n" + "\n".join(f"  {f.relative_to(WS_ROBERTO)}" for f in fs[:30])


# ============================================================
# TOOLS - CURIOSO
# ============================================================

class ToolBuscarWeb(BaseTool):
    name: str = "buscar_web"
    description: str = "Pesquisa na internet via DuckDuckGo. Param: query (str). Retorna titulo, resumo e link."
    def _run(self, query: str = "", **kw) -> str:
        q = query or kw.get("search_query", kw.get("term", kw.get("search", "")))
        if not q:
            return "ERRO: query vazio"
        try:
            from duckduckgo_search import DDGS
            res = []
            with DDGS() as ddgs:
                for r in ddgs.text(q, max_results=5):
                    res.append(
                        f"TITULO: {r['title']}\n"
                        f"RESUMO: {r['body'][:300]}\n"
                        f"LINK: {r['href']}"
                    )
            return "\n\n".join(res) if res else f"Nenhum resultado para: {q}"
        except Exception as e:
            return f"ERRO: {e}"


class ToolLerPagina(BaseTool):
    name: str = "ler_pagina"
    description: str = "Acessa URL e extrai texto. Param: url (str com https://)"
    def _run(self, url: str = "", **kw) -> str:
        u = url or kw.get("page_url", kw.get("link", ""))
        if not u:
            return "ERRO: url vazio"
        try:
            r = requests.get(u, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
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
            p = TE(); p.feed(r.text)
            text = "\n".join(p.parts)
            return text[:4000] if text else "Pagina sem conteudo"
        except Exception as e:
            return f"ERRO: {e}"


class ToolSalvarPesquisa(BaseTool):
    name: str = "salvar_pesquisa"
    description: str = "Salva pesquisa em arquivo. Params: filename (str), content (str)"
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", f"pesquisa_{datetime.now():%Y%m%d_%H%M}.md")
        ct = content or kw.get("text", kw.get("data", ""))
        try:
            (WS_CURIOSO / fn).write_text(ct, encoding="utf-8")
            return f"OK salvo: {fn}"
        except Exception as e:
            return f"ERRO: {e}"


# ============================================================
# TOOLS - MARLEY
# ============================================================

class ToolGerarImagem(BaseTool):
    name: str = "gerar_imagem"
    description: str = (
        "Gera imagem REAL com IA via Pollinations. "
        "Param: prompt (str em INGLES, 30-100 palavras descrevendo a imagem). "
        "Retorna IMAGE_GENERATED com url e path."
    )
    def _run(self, prompt: str = "", **kw) -> str:
        p = prompt or kw.get("image_prompt", kw.get("description", kw.get("text", "")))
        if not p:
            return "ERRO: prompt vazio"
        try:
            encoded = requests.utils.quote(p)
            url = (
                f"https://gen.pollinations.ai/image/{encoded}"
                f"?width=1024&height=1024&nologo=true&enhance=true"
            )
            print(f"[MARLEY] Gerando imagem...")
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code == 200:
                data = b"".join(resp.iter_content(8192))
                if len(data) < 500:
                    return f"ERRO: imagem muito pequena ({len(data)} bytes)"
                nm = f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
                fp = WS_MARLEY / nm
                fp.write_bytes(data)
                print(f"[MARLEY] Salvo: {fp} ({len(data)} bytes)")
                return f"IMAGE_GENERATED url={url} path={fp} size={len(data)}"
            return f"ERRO: HTTP {resp.status_code}"
        except requests.Timeout:
            return "ERRO: timeout 120s"
        except Exception as e:
            return f"ERRO: {e}"


class ToolCriarTemplate(BaseTool):
    name: str = "criar_template"
    description: str = "Cria template HTML/SVG. Params: filename (str), content (str)"
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "template.html")
        ct = content or kw.get("code", kw.get("html_content", kw.get("html", "")))
        try:
            (WS_MARLEY / fn).write_text(ct, encoding="utf-8")
            return f"OK template: {fn}"
        except Exception as e:
            return f"ERRO: {e}"


# ============================================================
# AGENTES
# ============================================================

roberto = Agent(
    role="Roberto - Senior Software Engineer",
    goal=(
        "Entregar projetos de software COMPLETOS e FUNCIONAIS. "
        "NUNCA dar passo-a-passo ou tutorial. "
        "SEMPRE usar criar_arquivo para criar cada arquivo. "
        "SEMPRE usar executar_python para testar."
    ),
    backstory=(
        "Sou Roberto, engenheiro senior com 15 anos de experiencia. "
        "Meu metodo: recebo tarefa, crio TODOS os arquivos com criar_arquivo, "
        "testo com executar_python, corrijo bugs, entrego PRONTO. "
        "Nunca dou instrucoes - eu FACO o trabalho."
    ),
    llm=llm, verbose=False, allow_delegation=False, max_iter=8,
    tools=[ToolCriarArquivo(), ToolExecutarPython(), ToolBash(),
           ToolLerArquivo(), ToolListarWS()],
)

curioso = Agent(
    role="Curioso - Research Analyst",
    goal=(
        "Pesquisar na internet usando buscar_web e entregar "
        "APENAS dados reais com links. PROIBIDO inventar."
    ),
    backstory=(
        "Sou Curioso, analista com acesso a internet. "
        "REGRA: SEMPRE chamo buscar_web ANTES de responder. "
        "NUNCA invento dados. Se nao encontro, digo claramente. "
        "Processo: buscar_web > ler resultados > responder com fontes."
    ),
    llm=llm, verbose=False, allow_delegation=False, max_iter=6,
    tools=[ToolBuscarWeb(), ToolLerPagina(), ToolSalvarPesquisa()],
)

marley = Agent(
    role="Marley - AI Image Artist",
    goal=(
        "GERAR imagens reais usando gerar_imagem. "
        "NUNCA apenas descrever. Prompt em INGLES."
    ),
    backstory=(
        "Sou Marley, artista IA. Quando pedem imagem, "
        "SEMPRE uso gerar_imagem com prompt detalhado em INGLES. "
        "Incluo: subject, style, lighting, colors, mood. "
        "NUNCA respondo sem gerar a imagem."
    ),
    llm=llm, verbose=False, allow_delegation=False, max_iter=4,
    tools=[ToolGerarImagem(), ToolCriarTemplate()],
)


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


def clean_thinking(text):
    cleaned = re.sub(r'<think>.*?</think>', '', str(text), flags=re.DOTALL).strip()
    return cleaned if cleaned else str(text).strip()


async def try_send_image(update, text):
    text = str(text)
    m = re.search(r'IMAGE_GENERATED\s+url=(\S+)\s+path=(\S+)', text)
    if m:
        url, lp = m.group(1), m.group(2)
        try:
            if os.path.exists(lp) and os.path.getsize(lp) > 500:
                with open(lp, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Imagem por Marley")
                return True
        except Exception:
            pass
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and len(r.content) > 500:
                await update.message.reply_photo(photo=BytesIO(r.content), caption="Imagem por Marley")
                return True
        except Exception:
            pass
        await update.message.reply_text(f"Imagem gerada:\n{url}")
        return True

    urls = re.findall(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', text)
    for u in urls[:1]:
        try:
            r = requests.get(u, timeout=90)
            if r.status_code == 200 and len(r.content) > 500:
                await update.message.reply_photo(photo=BytesIO(r.content), caption="Imagem por Marley")
                return True
        except Exception:
            pass
        await update.message.reply_text(f"Imagem:\n{u}")
        return True

    imgs = sorted(WS_MARLEY.glob("img_*.png"), reverse=True)
    if imgs and imgs[0].stat().st_size > 500:
        age = (datetime.now() - datetime.fromtimestamp(imgs[0].stat().st_mtime)).seconds
        if age < 180:
            try:
                with open(imgs[0], "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Imagem por Marley")
                return True
            except Exception:
                pass
    return False


def clean_image_refs(text):
    text = re.sub(r'IMAGE_GENERATED\s+url=\S+\s+path=\S+(\s+size=\d+)?', '[imagem enviada]', text)
    text = re.sub(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', '', text)
    return text.strip()


# ============================================================
# COMANDOS
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "=== IRONCORE AGENTS v5.0 ===\n"
        "LLM: DeepSeek V3\n\n"
        "[ROBERTO] Engenheiro de Software\n"
        "  /roberto [tarefa]\n\n"
        "[CURIOSO] Pesquisador & Analista\n"
        "  /curioso [pergunta]\n\n"
        "[MARLEY] Artista IA\n"
        "  /marley [descricao]\n\n"
        "[TEAM] 3 agentes juntos\n"
        "  /team [projeto]\n\n"
        "Outros: /status  /workspace  /limpar\n\n"
        "Exemplos:\n"
        "  /roberto crie API Flask com CRUD\n"
        "  /curioso tendencias IA 2026\n"
        "  /marley dragao cyberpunk\n"
        "  /team landing page fintech"
    )


async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/roberto [tarefa]")
        return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Roberto] {tarefa}\nTrabalhando...")
    task = Task(
        description=(
            f"TAREFA: {tarefa}\n\n"
            "OBRIGATORIO:\n"
            "1. Use criar_arquivo para criar cada arquivo\n"
            "2. Use executar_python para testar\n"
            "3. Corrija erros se houver\n"
            "4. Entregue COMPLETO\n"
            "5. NUNCA de passo-a-passo\n"
            "6. Liste arquivos criados no final"
        ),
        agent=roberto,
        expected_output="Projeto completo com arquivos criados e testados",
    )
    try:
        result = clean_thinking(run_crew_with_retry(
            Crew(agents=[roberto], tasks=[task], verbose=False)))
        await send_long(update, f"[Roberto]\n\n{result}")
    except Exception as e:
        print(f"[ERRO] Roberto: {e}")
        await update.message.reply_text(f"[Roberto] Erro: {str(e)[:400]}")


async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/curioso [pergunta]")
        return
    pergunta = " ".join(context.args)
    await update.message.reply_text(f"[Curioso] {pergunta}\nBuscando...")
    task = Task(
        description=(
            f"PESQUISE: {pergunta}\n\n"
            "OBRIGATORIO:\n"
            "1. Chame buscar_web com termos relevantes\n"
            "2. Leia os resultados\n"
            "3. Use ler_pagina se precisar mais detalhes\n"
            "4. Responda SOMENTE com dados da busca\n"
            "5. Cite fontes com links\n"
            "PROIBIDO responder sem buscar_web.\n"
            "PROIBIDO inventar dados."
        ),
        agent=curioso,
        expected_output="Dados reais da web com fontes",
    )
    try:
        result = clean_thinking(run_crew_with_retry(
            Crew(agents=[curioso], tasks=[task], verbose=False)))
        await send_long(update, f"[Curioso]\n\n{result}")
    except Exception as e:
        print(f"[ERRO] Curioso: {e}")
        await update.message.reply_text(f"[Curioso] Erro: {str(e)[:400]}")


async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/marley [descricao]")
        return
    pedido = " ".join(context.args)
    await update.message.reply_text(f"[Marley] {pedido}\nGerando...")
    task = Task(
        description=(
            f"IMAGEM PEDIDA: {pedido}\n\n"
            "OBRIGATORIO:\n"
            "1. Crie prompt em INGLES (50-100 palavras)\n"
            "2. Chame gerar_imagem com o prompt\n"
            "3. Reporte resultado\n"
            "PROIBIDO responder sem gerar_imagem."
        ),
        agent=marley,
        expected_output="IMAGE_GENERATED com url e path",
    )
    try:
        result = clean_thinking(run_crew_with_retry(
            Crew(agents=[marley], tasks=[task], verbose=False)))
        sent = await try_send_image(update, result)
        display = clean_image_refs(result) if sent else result
        if display.strip():
            await send_long(update, f"[Marley]\n\n{display}")
    except Exception as e:
        print(f"[ERRO] Marley: {e}")
        await update.message.reply_text(f"[Marley] Erro: {str(e)[:400]}")


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/team [projeto]")
        return
    projeto = " ".join(context.args)
    await update.message.reply_text(f"[Team] {projeto}\n3 agentes...")
    tasks = [
        Task(description=f"PROJETO: {projeto}\nVoce e ENGENHEIRO. Crie codigo com criar_arquivo e teste.",
             agent=roberto, expected_output="Codigo criado e testado"),
        Task(description=f"PROJETO: {projeto}\nVoce e PESQUISADOR. Use buscar_web. Dados reais com fontes.",
             agent=curioso, expected_output="Pesquisa com fontes"),
        Task(description=f"PROJETO: {projeto}\nVoce e CRIATIVO. Use gerar_imagem para visual.",
             agent=marley, expected_output="Imagem gerada"),
    ]
    try:
        result = clean_thinking(run_crew_with_retry(
            Crew(agents=[roberto, curioso, marley], tasks=tasks, verbose=False)))
        sent = await try_send_image(update, result)
        display = clean_image_refs(result) if sent else result
        await send_long(update, f"[Team]\n\n{display}")
    except Exception as e:
        print(f"[ERRO] Team: {e}")
        await update.message.reply_text(f"[Team] Erro: {str(e)[:400]}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = len([f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")])
    cc = len([f for f in WS_CURIOSO.rglob("*") if f.is_file()])
    mc = len([f for f in WS_MARLEY.rglob("*") if f.is_file()])
    await update.message.reply_text(
        f"=== IRONCORE AGENTS v5.0 ===\n"
        f"LLM: DeepSeek V3\n"
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
    print("IRONCORE AGENTS v5.0")
    print("LLM: DeepSeek V3")
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
