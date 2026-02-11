# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v5.0 - Final
Roberto (Engenheiro) | Curioso (Pesquisador) | Marley (Criativo)
LLM: Llama 3.3 70B via Groq (Dev Tier)
Deploy: Render.com Background Worker
"""

import os
import re
import sys
import time
import logging
import subprocess
from datetime import datetime
from io import BytesIO
from pathlib import Path

# Suppress LiteLLM noise BEFORE any imports
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("litellm").setLevel(logging.CRITICAL)
logging.getLogger("crewai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

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

BASE_DIR = Path(__file__).resolve().parent.parent
WS_ROBERTO = BASE_DIR / "workspace" / "roberto"
WS_CURIOSO = BASE_DIR / "workspace" / "curioso"
WS_MARLEY = BASE_DIR / "workspace" / "marley"

for d in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY):
    d.mkdir(parents=True, exist_ok=True)

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    temperature=0.3,
)


# ============================================================
# TOOLS - ROBERTO
# ============================================================

class ToolCriarArquivo(BaseTool):
    name: str = "criar_arquivo"
    description: str = "Cria arquivo no workspace. Params: filename (str), content (str)"

    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", kw.get("name", "output.py"))
        ct = content or kw.get("code", kw.get("file_content", ""))
        try:
            p = WS_ROBERTO / fn
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ct, encoding="utf-8")
            return f"OK criado: {fn} ({len(ct)} bytes)"
        except Exception as e:
            return f"ERRO: {e}"


class ToolExecutarPython(BaseTool):
    name: str = "executar_python"
    description: str = "Executa codigo Python e retorna output. Param: code (str)"

    def _run(self, code: str = "", **kw) -> str:
        c = code or kw.get("script", kw.get("python_code", ""))
        try:
            f = WS_ROBERTO / "_run.py"
            f.write_text(c, encoding="utf-8")
            r = subprocess.run(
                ["python3", str(f)], capture_output=True,
                text=True, timeout=30, cwd=str(WS_ROBERTO)
            )
            o = ""
            if r.stdout:
                o += r.stdout
            if r.stderr:
                o += "\nSTDERR:\n" + r.stderr
            return (o.strip() or "OK executado sem output")[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO: timeout 30s"
        except Exception as e:
            return f"ERRO: {e}"


class ToolBash(BaseTool):
    name: str = "executar_bash"
    description: str = "Executa comando shell/bash. Param: command (str)"

    def _run(self, command: str = "", **kw) -> str:
        cmd = command or kw.get("cmd", "")
        blocked = ["rm -rf /", "mkfs", "dd if=", ":(){", "fork"]
        if any(x in cmd for x in blocked):
            return "ERRO: comando bloqueado por seguranca"
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
                return f"ERRO: arquivo nao encontrado: {fn}"
            return p.read_text(encoding="utf-8")[:4000]
        except Exception as e:
            return f"ERRO: {e}"


class ToolListarWS(BaseTool):
    name: str = "listar_workspace"
    description: str = "Lista todos os arquivos do workspace Roberto"

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
    description: str = "Pesquisa na internet. Param: query (str). Retorna 5 resultados."

    def _run(self, query: str = "", **kw) -> str:
        q = query or kw.get("search_query", kw.get("term", ""))
        if not q:
            return "ERRO: query vazia"
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(q, max_results=5):
                    results.append(
                        f"TITULO: {r['title']}\n"
                        f"RESUMO: {r['body'][:300]}\n"
                        f"LINK: {r['href']}"
                    )
            if not results:
                return "Nenhum resultado encontrado para: " + q
            return "\n\n".join(results)
        except Exception as e:
            return f"ERRO na busca: {e}"


class ToolLerPagina(BaseTool):
    name: str = "ler_pagina"
    description: str = "Acessa URL e extrai texto. Param: url (str com https://)"

    def _run(self, url: str = "", **kw) -> str:
        u = url or kw.get("page_url", kw.get("link", ""))
        if not u:
            return "ERRO: url vazia"
        try:
            resp = requests.get(u, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.parts = []
                    self.skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "nav", "footer", "header"):
                        self.skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer", "header"):
                        self.skip = False

                def handle_data(self, data):
                    if not self.skip and data.strip():
                        self.parts.append(data.strip())

            parser = TextExtractor()
            parser.feed(resp.text)
            text = "\n".join(parser.parts)
            return text[:4000] if text else "Pagina sem conteudo de texto"
        except Exception as e:
            return f"ERRO ao acessar pagina: {e}"


class ToolSalvarPesquisa(BaseTool):
    name: str = "salvar_pesquisa"
    description: str = "Salva resultado no workspace. Params: filename (str), content (str)"

    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", f"pesq_{datetime.now():%Y%m%d_%H%M}.md")
        ct = content or kw.get("text", "")
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
        "Gera imagem REAL com IA (Pollinations, gratis). "
        "Param: prompt (str em INGLES, 30-100 palavras detalhadas). "
        "Retorna IMAGE_GENERATED com url e path do arquivo."
    )

    def _run(self, prompt: str = "", **kw) -> str:
        p = prompt or kw.get("image_prompt", kw.get("description", ""))
        if not p:
            return "ERRO: prompt vazio"
        try:
            encoded = requests.utils.quote(p)
            url = (
                f"https://gen.pollinations.ai/image/{encoded}"
                f"?width=1024&height=1024&nologo=true&enhance=true"
            )
            print(f"[MARLEY] Gerando imagem: {p[:80]}...")
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code == 200:
                data = b"".join(resp.iter_content(8192))
                if len(data) < 500:
                    return f"ERRO: imagem muito pequena ({len(data)} bytes)"
                img_name = f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
                img_path = WS_MARLEY / img_name
                img_path.write_bytes(data)
                print(f"[MARLEY] Salvo: {img_path} ({len(data)} bytes)")
                return f"IMAGE_GENERATED url={url} path={img_path} size={len(data)}"
            return f"ERRO: HTTP {resp.status_code}"
        except requests.Timeout:
            return "ERRO: timeout gerando imagem (tente novamente)"
        except Exception as e:
            return f"ERRO: {e}"


class ToolCriarTemplate(BaseTool):
    name: str = "criar_template"
    description: str = "Cria template HTML/SVG. Params: filename (str), content (str)"

    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "template.html")
        ct = content or kw.get("code", kw.get("html_content", ""))
        try:
            (WS_MARLEY / fn).write_text(ct, encoding="utf-8")
            return f"OK template criado: {fn}"
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
        "SEMPRE usar criar_arquivo para criar codigo e executar_python para testar."
    ),
    backstory=(
        "Sou Roberto, engenheiro de software senior com 15 anos de experiencia. "
        "Meu metodo: recebo a tarefa, CRIO todos os arquivos com criar_arquivo, "
        "TESTO com executar_python, corrijo erros, e entrego PRONTO. "
        "Eu NUNCA explico passo-a-passo. Eu FACO o trabalho. "
        "Minhas ferramentas: criar_arquivo, executar_python, executar_bash, "
        "ler_arquivo, listar_workspace."
    ),
    llm=llm,
    verbose=False,
    allow_delegation=False,
    max_iter=10,
    tools=[ToolCriarArquivo(), ToolExecutarPython(), ToolBash(),
           ToolLerArquivo(), ToolListarWS()],
)

curioso = Agent(
    role="Curioso - Research Analyst & Web Researcher",
    goal=(
        "Pesquisar na internet usando buscar_web e entregar "
        "SOMENTE dados encontrados na busca real. PROIBIDO inventar."
    ),
    backstory=(
        "Sou Curioso, pesquisador com acesso a internet. "
        "REGRA 1: SEMPRE uso buscar_web ANTES de responder qualquer pergunta. "
        "REGRA 2: NUNCA invento dados, numeros, estatisticas ou fontes. "
        "REGRA 3: Se nao encontro, digo 'nao encontrei dados sobre isso'. "
        "Meu processo: buscar_web > ler resultados > ler_pagina se preciso > "
        "montar resposta SOMENTE com dados reais > citar fontes com links."
    ),
    llm=llm,
    verbose=False,
    allow_delegation=False,
    max_iter=8,
    tools=[ToolBuscarWeb(), ToolLerPagina(), ToolSalvarPesquisa()],
)

marley = Agent(
    role="Marley - Creative Director & AI Image Artist",
    goal=(
        "GERAR imagens reais usando a ferramenta gerar_imagem. "
        "NUNCA apenas descrever - SEMPRE gerar usando a ferramenta."
    ),
    backstory=(
        "Sou Marley, artista de IA que GERA imagens de verdade. "
        "REGRA 1: Quando pedem imagem, eu SEMPRE uso gerar_imagem. "
        "REGRA 2: Eu NUNCA apenas descrevo. Eu GERO. "
        "REGRA 3: O prompt para gerar_imagem DEVE ser em INGLES, "
        "detalhado com 50-100 palavras incluindo: subject, style, "
        "lighting, colors, composition, mood, quality keywords. "
        "Exemplo: 'A majestic cyberpunk dragon flying over "
        "a neon-lit cityscape at night, metallic scales reflecting purple "
        "and blue neon lights, dramatic composition, cinematic lighting, "
        "highly detailed, 8k quality, digital art style'"
    ),
    llm=llm,
    verbose=False,
    allow_delegation=False,
    max_iter=5,
    tools=[ToolGerarImagem(), ToolCriarTemplate()],
)


# ============================================================
# HELPERS
# ============================================================

def split_msg(text, max_len=4000):
    text = str(text).strip()
    if not text:
        return ["(sem resposta)"]
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 <= max_len:
            current += para + "\n\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            if len(para) > max_len:
                for i in range(0, len(para), max_len):
                    chunks.append(para[i:i + max_len])
                current = ""
            else:
                current = para + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_len]]


async def send_long(update, text):
    parts = split_msg(text)
    for i, chunk in enumerate(parts):
        try:
            prefix = f"(parte {i + 1}/{len(parts)})\n\n" if len(parts) > 1 and i > 0 else ""
            await update.message.reply_text(prefix + chunk)
        except Exception:
            try:
                await update.message.reply_text(chunk[:4000])
            except Exception:
                pass


def clean_response(text):
    text = str(text)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def try_send_image(update, result_text):
    text = str(result_text)

    match = re.search(r'IMAGE_GENERATED\s+url=(\S+)\s+path=(\S+)', text)
    if match:
        url = match.group(1)
        local_path = match.group(2)

        try:
            if os.path.exists(local_path) and os.path.getsize(local_path) > 500:
                with open(local_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Imagem por Marley")
                return True
        except Exception:
            pass

        try:
            resp = requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 500:
                await update.message.reply_photo(
                    photo=BytesIO(resp.content), caption="Imagem por Marley"
                )
                return True
        except Exception:
            pass

        try:
            await update.message.reply_text(f"Imagem gerada:\n{url}")
        except Exception:
            pass
        return True

    urls = re.findall(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', text)
    for url in urls[:1]:
        try:
            resp = requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 500:
                await update.message.reply_photo(
                    photo=BytesIO(resp.content), caption="Imagem por Marley"
                )
                return True
        except Exception:
            pass
        try:
            await update.message.reply_text(f"Imagem:\n{url}")
        except Exception:
            pass
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


def run_crew_safe(agents, tasks, max_retries=3):
    """Executa Crew com retry automatico para rate limits."""
    crew = Crew(agents=agents, tasks=tasks, verbose=False)
    for attempt in range(max_retries):
        try:
            result = crew.kickoff()
            return clean_response(str(result))
        except Exception as e:
            err = str(e).lower()
            if "rate_limit" in err or "429" in err:
                wait = min(15 * (attempt + 1), 45)
                print(f"[RETRY] Rate limit. Aguardando {wait}s (tentativa {attempt + 1})")
                time.sleep(wait)
                continue
            raise
    return "Erro: limite de tentativas (rate limit). Tente novamente em 1 minuto."


# ============================================================
# COMANDOS TELEGRAM
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "IRONCORE AGENTS v5.0\n"
        "LLM: Llama 3.3 70B via Groq\n\n"
        "[ROBERTO] Engenheiro de Software\n"
        "  Cria projetos completos, executa e testa codigo\n"
        "  /roberto [tarefa]\n\n"
        "[CURIOSO] Pesquisador & Analista\n"
        "  Pesquisa web real com fontes verificadas\n"
        "  /curioso [pergunta]\n\n"
        "[MARLEY] Diretor Criativo & Artista IA\n"
        "  Gera imagens reais com inteligencia artificial\n"
        "  /marley [descricao visual]\n\n"
        "[TEAM] Colaboracao dos 3 Agentes\n"
        "  /team [projeto]\n\n"
        "Outros comandos:\n"
        "  /status - Ver status dos agentes\n"
        "  /workspace - Ver arquivos dos workspaces\n"
        "  /limpar - Limpar todos os workspaces"
    )


async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /roberto [tarefa]\nEx: /roberto crie script que analisa CSV")
        return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Roberto] Recebeu: {tarefa}\nTrabalhando...")
    task = Task(
        description=(
            f"TAREFA: {tarefa}\n\n"
            "INSTRUCOES (siga na ordem):\n"
            "1. Use criar_arquivo para criar cada arquivo necessario\n"
            "2. Use executar_python para testar o codigo principal\n"
            "3. Se der erro, corrija e teste novamente\n"
            "4. Use listar_workspace para confirmar os arquivos criados\n"
            "5. Entregue relatorio do que foi criado e testado\n\n"
            "PROIBIDO: dar passo-a-passo, tutorial ou instrucoes.\n"
            "Voce DEVE criar e testar o codigo.\n"
            "Assine: -- Roberto"
        ),
        agent=roberto,
        expected_output="Projeto completo com arquivos criados e testados",
    )
    try:
        result = run_crew_safe([roberto], [task])
        await send_long(update, f"[Roberto]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro Roberto: {str(e)[:500]}")


async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /curioso [pergunta]\nEx: /curioso tendencias IA 2026")
        return
    pergunta = " ".join(context.args)
    await update.message.reply_text(f"[Curioso] Pesquisando: {pergunta}\nBuscando na web...")
    task = Task(
        description=(
            f"PESQUISA: {pergunta}\n\n"
            "INSTRUCOES (siga na ordem):\n"
            "1. Use buscar_web com palavras-chave da pergunta\n"
            "2. Leia os resultados retornados\n"
            "3. Se precisar mais detalhes, use ler_pagina nos links\n"
            "4. Monte sua resposta SOMENTE com dados da busca\n"
            "5. Cite as fontes (links) no final\n\n"
            "PROIBIDO: responder sem ter usado buscar_web.\n"
            "PROIBIDO: inventar dados, numeros ou fontes.\n"
            "Assine: -- Curioso"
        ),
        agent=curioso,
        expected_output="Resposta com dados reais da web e links das fontes",
    )
    try:
        result = run_crew_safe([curioso], [task])
        await send_long(update, f"[Curioso]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro Curioso: {str(e)[:500]}")


async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /marley [descricao]\nEx: /marley dragao cyberpunk")
        return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Marley] Criando: {tarefa}\nGerando imagem...")
    task = Task(
        description=(
            f"PEDIDO: {tarefa}\n\n"
            "INSTRUCOES (siga na ordem):\n"
            "1. Crie prompt DETALHADO em INGLES (50-100 palavras)\n"
            "   Inclua: subject, style, lighting, colors, composition, mood\n"
            "2. Use gerar_imagem passando o prompt em ingles\n"
            "3. Reporte o resultado\n\n"
            "PROIBIDO: responder sem usar gerar_imagem.\n"
            "PROIBIDO: apenas descrever sem gerar.\n"
            "Voce TEM a ferramenta gerar_imagem. USE-A AGORA.\n"
            "Assine: -- Marley"
        ),
        agent=marley,
        expected_output="Resultado contendo IMAGE_GENERATED com url e path",
    )
    try:
        result = run_crew_safe([marley], [task])
        sent = await try_send_image(update, result)
        if sent:
            result = re.sub(
                r'IMAGE_GENERATED\s+url=\S+\s+path=\S+(\s+size=\d+)?',
                '[imagem enviada acima]', result
            )
            result = re.sub(
                r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', '', result
            )
        await send_long(update, f"[Marley]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro Marley: {str(e)[:500]}")


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /team [projeto]\nEx: /team landing page fintech")
        return
    projeto = " ".join(context.args)
    await update.message.reply_text(f"[Team] Projeto: {projeto}\n3 agentes trabalhando...")
    tasks = [
        Task(
            description=(
                f"PROJETO: {projeto}\n"
                "ENGENHEIRO: Crie codigo com criar_arquivo e teste. -- Roberto"
            ),
            agent=roberto, expected_output="Codigo criado e testado"),
        Task(
            description=(
                f"PROJETO: {projeto}\n"
                "PESQUISADOR: Use buscar_web para dados de mercado. -- Curioso"
            ),
            agent=curioso, expected_output="Pesquisa com fontes"),
        Task(
            description=(
                f"PROJETO: {projeto}\n"
                "CRIATIVO: Use gerar_imagem para visual do projeto. -- Marley"
            ),
            agent=marley, expected_output="Imagem gerada"),
    ]
    try:
        result = run_crew_safe([roberto, curioso, marley], tasks)
        sent = await try_send_image(update, result)
        if sent:
            result = re.sub(
                r'IMAGE_GENERATED\s+url=\S+\s+path=\S+(\s+size=\d+)?',
                '[imagem enviada]', result
            )
        await send_long(update, f"[Team]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro Team: {str(e)[:500]}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc = len([f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")])
    cc = len([f for f in WS_CURIOSO.rglob("*") if f.is_file()])
    mc = len([f for f in WS_MARLEY.rglob("*") if f.is_file()])
    await update.message.reply_text(
        f"IRONCORE AGENTS v5.0\n"
        f"LLM: Llama 3.3 70B via Groq\n"
        f"Horario: {datetime.now():%d/%m/%Y %H:%M}\n\n"
        f"[Roberto] ONLINE | {rc} arquivo(s)\n"
        f"  criar_arquivo, executar_python, executar_bash, ler_arquivo, listar_workspace\n\n"
        f"[Curioso] ONLINE | {cc} arquivo(s)\n"
        f"  buscar_web, ler_pagina, salvar_pesquisa\n\n"
        f"[Marley] ONLINE | {mc} arquivo(s)\n"
        f"  gerar_imagem, criar_template\n\n"
        f"Todos operacionais."
    )


async def cmd_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "WORKSPACES\n\n"
    for name, ws in [("Roberto", WS_ROBERTO), ("Curioso", WS_CURIOSO), ("Marley", WS_MARLEY)]:
        files = [f for f in ws.rglob("*") if f.is_file() and not f.name.startswith("_")]
        msg += f"--- {name} ---\n"
        if files:
            for f in files[:10]:
                msg += f"  {f.relative_to(ws)} ({f.stat().st_size:,}b)\n"
            if len(files) > 10:
                msg += f"  +{len(files) - 10} mais\n"
        else:
            msg += "  (vazio)\n"
        msg += "\n"
    await update.message.reply_text(msg)


async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = 0
    for ws in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY):
        for f in ws.rglob("*"):
            if f.is_file():
                f.unlink()
                n += 1
    await update.message.reply_text(f"{n} arquivo(s) removido(s) dos workspaces.")


async def error_handler(update, context):
    err = str(context.error)
    if "Conflict" in err:
        print("[WARN] Conflito polling - instancia duplicada")
    elif "Timed" in err or "Network" in err:
        print(f"[WARN] Rede: {err[:80]}")
    else:
        print(f"[ERROR] {err[:200]}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("IRONCORE AGENTS v5.0")
    print(f"LLM: Llama 3.3 70B via Groq")
    print(f"Data: {datetime.now():%d/%m/%Y %H:%M:%S}")
    print("=" * 50)
    print()
    print(f"Roberto  | Engenheiro  | {WS_ROBERTO}")
    print(f"Curioso  | Pesquisador | {WS_CURIOSO}")
    print(f"Marley   | Criativo    | {WS_MARLEY}")
    print()

    if not GROQ_API_KEY:
        print("[FATAL] GROQ_API_KEY nao definida!")
        sys.exit(1)
    if not TELEGRAM_BOT_TOKEN:
        print("[FATAL] TELEGRAM_BOT_TOKEN nao definido!")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("roberto", cmd_roberto))
    app.add_handler(CommandHandler("curioso", cmd_curioso))
    app.add_handler(CommandHandler("marley", cmd_marley))
    app.add_handler(CommandHandler("team", cmd_team))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("workspace", cmd_workspace))
    app.add_handler(CommandHandler("limpar", cmd_limpar))
    app.add_error_handler(error_handler)

    print("Bot configurado. Aguardando Telegram...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
