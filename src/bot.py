# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v4.0
Roberto (Engenheiro) | Curioso (Pesquisador) | Marley (Criativo)
LLM: DeepSeek R1 Distill 70B via Groq
Deploy: Render.com Background Worker
"""

import os
import re
import subprocess
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool

# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

os.environ["LITELLM_LOG"] = "ERROR"
os.environ["CREWAI_TRACING_ENABLED"] = "false"

BASE_DIR = Path(__file__).resolve().parent.parent
WS_ROBERTO = BASE_DIR / "workspace" / "roberto"
WS_CURIOSO = BASE_DIR / "workspace" / "curioso"
WS_MARLEY = BASE_DIR / "workspace" / "marley"

for d in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY):
    d.mkdir(parents=True, exist_ok=True)

llm = LLM(
    model="groq/deepseek-r1-distill-llama-70b",
    api_key=GROQ_API_KEY,
    temperature=0.3,
)


# ============================================================
# TOOLS - ROBERTO
# ============================================================

class ToolCriarArquivo(BaseTool):
    name: str = "criar_arquivo"
    description: str = "Cria arquivo no workspace. Params: filename, content"
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "output.py")
        ct = content or kw.get("code", kw.get("file_content", ""))
        try:
            p = WS_ROBERTO / fn
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ct, encoding="utf-8")
            return f"OK criado: {fn} ({len(ct)}b)"
        except Exception as e:
            return f"ERRO {e}"


class ToolExecutarPython(BaseTool):
    name: str = "executar_python"
    description: str = "Executa codigo Python e retorna resultado. Param: code"
    def _run(self, code: str = "", **kw) -> str:
        c = code or kw.get("script", kw.get("python_code", ""))
        try:
            f = WS_ROBERTO / "_run.py"
            f.write_text(c, encoding="utf-8")
            r = subprocess.run(["python3", str(f)], capture_output=True,
                               text=True, timeout=30, cwd=str(WS_ROBERTO))
            o = (r.stdout + "\n" + r.stderr).strip()
            return (o or "OK sem output")[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO timeout 30s"
        except Exception as e:
            return f"ERRO {e}"


class ToolBash(BaseTool):
    name: str = "executar_bash"
    description: str = "Executa comando shell. Param: command"
    def _run(self, command: str = "", **kw) -> str:
        cmd = command or kw.get("cmd", "")
        if any(x in cmd for x in ["rm -rf /", "mkfs", ":(){"]):
            return "ERRO bloqueado"
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=30, cwd=str(WS_ROBERTO))
            return ((r.stdout + "\n" + r.stderr).strip() or "OK")[:3000]
        except Exception as e:
            return f"ERRO {e}"


class ToolLerArquivo(BaseTool):
    name: str = "ler_arquivo"
    description: str = "Le arquivo do workspace. Param: filename"
    def _run(self, filename: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "")
        try:
            p = WS_ROBERTO / fn
            return p.read_text(encoding="utf-8")[:4000] if p.exists() else f"ERRO nao existe: {fn}"
        except Exception as e:
            return f"ERRO {e}"


class ToolListarWS(BaseTool):
    name: str = "listar_workspace"
    description: str = "Lista arquivos do workspace Roberto"
    def _run(self, **kw) -> str:
        fs = [f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")]
        return "\n".join(str(f.relative_to(WS_ROBERTO)) for f in fs[:30]) or "vazio"


# ============================================================
# TOOLS - CURIOSO
# ============================================================

class ToolBuscarWeb(BaseTool):
    name: str = "buscar_web"
    description: str = "Pesquisa na internet via DuckDuckGo. Param: query"
    def _run(self, query: str = "", **kw) -> str:
        q = query or kw.get("search_query", kw.get("term", ""))
        try:
            from duckduckgo_search import DDGS
            res = []
            with DDGS() as ddgs:
                for r in ddgs.text(q, max_results=5):
                    res.append(f"* {r['title']}\n  {r['body'][:250]}\n  {r['href']}")
            return "\n\n".join(res) if res else "Nenhum resultado"
        except Exception as e:
            return f"ERRO {e}"


class ToolLerPagina(BaseTool):
    name: str = "ler_pagina"
    description: str = "Acessa URL e extrai texto. Param: url"
    def _run(self, url: str = "", **kw) -> str:
        u = url or kw.get("page_url", kw.get("link", ""))
        try:
            r = requests.get(u, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            from html.parser import HTMLParser
            class P(HTMLParser):
                def __init__(self):
                    super().__init__(); self.t=[]; self._s=False
                def handle_starttag(self,tag,a):
                    if tag in("script","style","nav","footer"): self._s=True
                def handle_endtag(self,tag):
                    if tag in("script","style","nav","footer"): self._s=False
                def handle_data(self,d):
                    if not self._s and d.strip(): self.t.append(d.strip())
            p=P(); p.feed(r.text)
            return "\n".join(p.t)[:4000]
        except Exception as e:
            return f"ERRO {e}"


class ToolSalvarPesquisa(BaseTool):
    name: str = "salvar_pesquisa"
    description: str = "Salva pesquisa em arquivo. Params: filename, content"
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", f"pesq_{datetime.now():%Y%m%d_%H%M}.md")
        ct = content or kw.get("text", "")
        try:
            (WS_CURIOSO / fn).write_text(ct, encoding="utf-8")
            return f"OK salvo: {fn}"
        except Exception as e:
            return f"ERRO {e}"


# ============================================================
# TOOLS - MARLEY
# ============================================================

class ToolGerarImagem(BaseTool):
    name: str = "gerar_imagem"
    description: str = (
        "Gera imagem REAL com IA via Pollinations. "
        "Param: prompt (descricao em INGLES, 30-100 palavras). "
        "Retorna IMAGE_GENERATED com url e path."
    )
    def _run(self, prompt: str = "", **kw) -> str:
        p = prompt or kw.get("image_prompt", kw.get("description", ""))
        try:
            enc = requests.utils.quote(p)
            url = f"https://gen.pollinations.ai/image/{enc}?width=1024&height=1024&nologo=true&enhance=true"
            print(f"[MARLEY] Gerando...")
            r = requests.get(url, timeout=120, stream=True)
            if r.status_code == 200:
                data = b"".join(r.iter_content(8192))
                if len(data) < 500:
                    return "ERRO imagem muito pequena"
                nm = f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
                fp = WS_MARLEY / nm
                fp.write_bytes(data)
                return f"IMAGE_GENERATED url={url} path={fp} size={len(data)}"
            return f"ERRO HTTP {r.status_code}"
        except Exception as e:
            return f"ERRO {e}"


class ToolCriarTemplate(BaseTool):
    name: str = "criar_template"
    description: str = "Cria template HTML/SVG. Params: filename, content"
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "template.html")
        ct = content or kw.get("code", kw.get("html_content", ""))
        try:
            (WS_MARLEY / fn).write_text(ct, encoding="utf-8")
            return f"OK template: {fn}"
        except Exception as e:
            return f"ERRO {e}"


# ============================================================
# AGENTES
# ============================================================

roberto = Agent(
    role="Roberto - Senior Software Engineer",
    goal="Entregar codigo COMPLETO e FUNCIONAL. NUNCA dar passo-a-passo.",
    backstory=(
        "Sou Roberto, engenheiro senior. "
        "Eu CRIO arquivos com criar_arquivo, TESTO com executar_python, "
        "e entrego PRONTO. Nunca dou tutorial. Eu FACO."
    ),
    llm=llm, verbose=False, allow_delegation=False,
    tools=[ToolCriarArquivo(), ToolExecutarPython(), ToolBash(),
           ToolLerArquivo(), ToolListarWS()],
)

curioso = Agent(
    role="Curioso - Research Analyst",
    goal="Pesquisar na web REAL usando buscar_web. PROIBIDO inventar dados.",
    backstory=(
        "Sou Curioso. Eu SEMPRE uso buscar_web antes de responder. "
        "NUNCA invento dados. Se nao encontro, digo que nao encontrei. "
        "Tudo que sei vem de buscar_web. Sem excecao."
    ),
    llm=llm, verbose=False, allow_delegation=False,
    tools=[ToolBuscarWeb(), ToolLerPagina(), ToolSalvarPesquisa()],
)

marley = Agent(
    role="Marley - AI Artist",
    goal="GERAR imagens usando gerar_imagem. NUNCA apenas descrever.",
    backstory=(
        "Sou Marley. Quando pedem imagem, eu SEMPRE uso gerar_imagem. "
        "Crio prompt em INGLES e chamo a ferramenta. "
        "NUNCA respondo sem gerar. A ferramenta faz o trabalho."
    ),
    llm=llm, verbose=False, allow_delegation=False,
    tools=[ToolGerarImagem(), ToolCriarTemplate()],
)


# ============================================================
# HELPERS
# ============================================================

def split_msg(text, mx=4000):
    text = str(text)
    if len(text) <= mx:
        return [text]
    chunks, cur = [], ""
    for p in text.split("\n\n"):
        if len(cur) + len(p) + 2 <= mx:
            cur += p + "\n\n"
        else:
            if cur: chunks.append(cur.strip())
            cur = (p + "\n\n") if len(p) <= mx else ""
            if len(p) > mx:
                for i in range(0, len(p), mx):
                    chunks.append(p[i:i+mx])
    if cur.strip(): chunks.append(cur.strip())
    return chunks or [text[:mx]]


async def send(update, text):
    for i, c in enumerate(split_msg(text)):
        try:
            pref = f"(pt {i+1})\n\n" if i > 0 else ""
            await update.message.reply_text(pref + c)
        except Exception:
            pass


def clean_thinking(text):
    """Remove <think>...</think> tags from DeepSeek R1 output."""
    return re.sub(r'<think>.*?</think>', '', str(text), flags=re.DOTALL).strip()


async def try_send_image(update, text):
    text = str(text)
    # Pattern: IMAGE_GENERATED url=X path=Y size=Z
    m = re.search(r'IMAGE_GENERATED\s+url=(\S+)\s+path=(\S+)', text)
    if m:
        url, lp = m.group(1), m.group(2)
        # Try local file
        try:
            if os.path.exists(lp) and os.path.getsize(lp) > 500:
                with open(lp, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Marley - Imagem gerada")
                return True
        except Exception:
            pass
        # Try URL download
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and len(r.content) > 500:
                await update.message.reply_photo(photo=BytesIO(r.content), caption="Marley - Imagem gerada")
                return True
        except Exception:
            pass
        await update.message.reply_text(f"Imagem gerada:\n{url}")
        return True

    # Fallback: find pollinations URLs
    urls = re.findall(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', text)
    for u in urls[:1]:
        try:
            r = requests.get(u, timeout=90)
            if r.status_code == 200 and len(r.content) > 500:
                await update.message.reply_photo(photo=BytesIO(r.content), caption="Marley - Imagem gerada")
                return True
        except Exception:
            pass
        await update.message.reply_text(f"Imagem:\n{u}")
        return True

    # Fallback: recent file in workspace
    imgs = sorted(WS_MARLEY.glob("img_*.png"), reverse=True)
    if imgs and imgs[0].stat().st_size > 500:
        age = (datetime.now() - datetime.fromtimestamp(imgs[0].stat().st_mtime)).seconds
        if age < 180:
            try:
                with open(imgs[0], "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Marley - Imagem gerada")
                return True
            except Exception:
                pass
    return False


# ============================================================
# COMANDOS
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "IRONCORE AGENTS v4.0\n"
        "LLM: DeepSeek R1 70B\n\n"
        "[ROBERTO] Engenheiro\n"
        "  Cria projetos completos, executa e testa codigo\n"
        "  /roberto [tarefa]\n\n"
        "[CURIOSO] Pesquisador\n"
        "  Pesquisa web real, analise com fontes\n"
        "  /curioso [pergunta]\n\n"
        "[MARLEY] Criativo\n"
        "  Gera imagens reais com IA\n"
        "  /marley [visual]\n\n"
        "[TEAM] Todos juntos\n"
        "  /team [projeto]\n\n"
        "Outros: /status /workspace /limpar"
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
            "1. Use criar_arquivo para criar todos os arquivos\n"
            "2. Use executar_python para testar\n"
            "3. Corrija erros se houver\n"
            "4. Entregue COMPLETO\n"
            "5. NUNCA de passo-a-passo\n"
            "Assine: -- Roberto"
        ),
        agent=roberto,
        expected_output="Arquivos criados e testados no workspace",
    )
    try:
        result = clean_thinking(str(Crew(agents=[roberto], tasks=[task], verbose=False).kickoff()))
        await send(update, f"[Roberto]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/curioso [pergunta]")
        return
    pergunta = " ".join(context.args)
    await update.message.reply_text(f"[Curioso] {pergunta}\nBuscando...")
    task = Task(
        description=(
            f"PESQUISA: {pergunta}\n\n"
            "OBRIGATORIO:\n"
            "1. Chame buscar_web com termos da pergunta\n"
            "2. Leia os resultados\n"
            "3. Se precisar, use ler_pagina nos links\n"
            "4. Responda SOMENTE com dados da busca\n"
            "5. Cite fontes/links\n"
            "PROIBIDO responder sem buscar_web.\n"
            "Assine: -- Curioso"
        ),
        agent=curioso,
        expected_output="Dados reais da web com fontes",
    )
    try:
        result = clean_thinking(str(Crew(agents=[curioso], tasks=[task], verbose=False).kickoff()))
        await send(update, f"[Curioso]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/marley [visual]")
        return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Marley] {tarefa}\nGerando...")
    task = Task(
        description=(
            f"PEDIDO: {tarefa}\n\n"
            "OBRIGATORIO:\n"
            "1. Crie prompt DETALHADO em INGLES (50-100 palavras)\n"
            "2. Chame gerar_imagem com o prompt\n"
            "3. Reporte o resultado\n"
            "PROIBIDO responder sem chamar gerar_imagem.\n"
            "Assine: -- Marley"
        ),
        agent=marley,
        expected_output="IMAGE_GENERATED com url e path",
    )
    try:
        result = clean_thinking(str(Crew(agents=[marley], tasks=[task], verbose=False).kickoff()))
        sent = await try_send_image(update, result)
        clean = result
        if sent:
            clean = re.sub(r'IMAGE_GENERATED\s+url=\S+\s+path=\S+\s*size=\d*', '[imagem enviada]', clean)
            clean = re.sub(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', '', clean)
        await send(update, f"[Marley]\n\n{clean}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/team [projeto]")
        return
    projeto = " ".join(context.args)
    await update.message.reply_text(f"[Team] {projeto}\n3 agentes trabalhando...")

    tasks = [
        Task(
            description=f"PROJETO: {projeto}\nVoce e ENGENHEIRO. Crie codigo com criar_arquivo. Teste. -- Roberto",
            agent=roberto, expected_output="Codigo criado"),
        Task(
            description=f"PROJETO: {projeto}\nVoce e PESQUISADOR. Use buscar_web. Dados reais. -- Curioso",
            agent=curioso, expected_output="Pesquisa com fontes"),
        Task(
            description=f"PROJETO: {projeto}\nVoce e CRIATIVO. Use gerar_imagem para visual. -- Marley",
            agent=marley, expected_output="Imagem gerada"),
    ]
    try:
        result = clean_thinking(str(Crew(agents=[roberto, curioso, marley],
                                         tasks=tasks, verbose=False).kickoff()))
        sent = await try_send_image(update, result)
        if sent:
            result = re.sub(r'IMAGE_GENERATED\s+url=\S+\s+path=\S+\s*size=\d*', '[imagem enviada]', result)
        await send(update, f"[Team]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = len([f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")])
    cc = len([f for f in WS_CURIOSO.rglob("*") if f.is_file()])
    mc = len([f for f in WS_MARLEY.rglob("*") if f.is_file()])
    await update.message.reply_text(
        f"IRONCORE AGENTS v4.0 - {datetime.now():%d/%m %H:%M}\n"
        f"LLM: DeepSeek R1 70B via Groq\n\n"
        f"[Roberto] ONLINE - {rc} arquivo(s)\n"
        f"  criar_arquivo, executar_python, executar_bash, ler_arquivo, listar_workspace\n\n"
        f"[Curioso] ONLINE - {cc} arquivo(s)\n"
        f"  buscar_web, ler_pagina, salvar_pesquisa\n\n"
        f"[Marley] ONLINE - {mc} arquivo(s)\n"
        f"  gerar_imagem, criar_template\n\n"
        f"Todos operacionais"
    )


async def cmd_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "WORKSPACES\n\n"
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
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("IRONCORE AGENTS v4.0")
    print("LLM: DeepSeek R1 Distill 70B via Groq")
    print(f"{datetime.now():%d/%m/%Y %H:%M:%S}")
    print("=" * 50)
    print(f"\nRoberto  | {WS_ROBERTO}")
    print(f"Curioso  | {WS_CURIOSO}")
    print(f"Marley   | {WS_MARLEY}")
    print("\nBot configurado. Aguardando Telegram...\n")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    for cmd, fn in [("start", cmd_start), ("roberto", cmd_roberto),
                    ("curioso", cmd_curioso), ("marley", cmd_marley),
                    ("team", cmd_team), ("status", cmd_status),
                    ("workspace", cmd_workspace), ("limpar", cmd_limpar)]:
        app.add_handler(CommandHandler(cmd, fn))
    app.run_polling()


if __name__ == "__main__":
    main()
