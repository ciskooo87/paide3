# -*- coding: utf-8 -*-
"""
IRONCORE AGENTS v3.2 - Time de Agentes IA para Telegram
Roberto (Engenheiro) | Curioso (Pesquisador) | Marley (Criativo)
Cada agente tem workspace proprio e ferramentas reais.
Deploy: Render.com Background Worker
"""

import os
import re
import subprocess
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool

# ============================================================
# CONFIGURACAO
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Silencia warnings do LiteLLM e desabilita tracing do CrewAI
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["CREWAI_TRACING_ENABLED"] = "false"

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE = BASE_DIR / "workspace"
WS_ROBERTO = WORKSPACE / "roberto"
WS_CURIOSO = WORKSPACE / "curioso"
WS_MARLEY = WORKSPACE / "marley"

for d in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY):
    d.mkdir(parents=True, exist_ok=True)

llm = LLM(
    model="groq/llama-3.1-8b-instant",
    api_key=GROQ_API_KEY,
    temperature=0.3,
)

# ============================================================
# FERRAMENTAS - ROBERTO
# ============================================================

class RobertoCreateFile(BaseTool):
    name: str = "criar_arquivo"
    description: str = (
        "Cria ou sobrescreve um arquivo no workspace do Roberto. "
        "Parametros: filename (ex: app.py) e content (conteudo completo do arquivo)."
    )
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", kw.get("name", "output.py"))
        ct = content or kw.get("file_content", kw.get("code", ""))
        try:
            path = WS_ROBERTO / fn
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(ct, encoding="utf-8")
            return f"OK Arquivo criado: workspace/roberto/{fn} ({len(ct)} bytes)"
        except Exception as e:
            return f"ERRO: {e}"


class RobertoExecuteCode(BaseTool):
    name: str = "executar_python"
    description: str = (
        "Executa codigo Python no workspace do Roberto e retorna o resultado. "
        "Parametro: code (codigo Python completo a ser executado)."
    )
    def _run(self, code: str = "", **kw) -> str:
        code = code or kw.get("python_code", kw.get("script", ""))
        try:
            tmp = WS_ROBERTO / "_run.py"
            tmp.write_text(code, encoding="utf-8")
            r = subprocess.run(
                ["python3", str(tmp)],
                capture_output=True, text=True, timeout=30,
                cwd=str(WS_ROBERTO),
            )
            out = ""
            if r.stdout:
                out += r.stdout
            if r.stderr:
                out += f"\nSTDERR:\n{r.stderr}"
            return (out or "OK executado sem output").strip()[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO Timeout (30s)"
        except Exception as e:
            return f"ERRO {e}"


class RobertoReadFile(BaseTool):
    name: str = "ler_arquivo"
    description: str = (
        "Le o conteudo de um arquivo do workspace do Roberto. "
        "Parametro: filename (caminho relativo, ex: app.py)."
    )
    def _run(self, filename: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", kw.get("path", ""))
        try:
            path = WS_ROBERTO / fn
            if not path.exists():
                return f"ERRO nao encontrado: {fn}"
            return path.read_text(encoding="utf-8")[:4000]
        except Exception as e:
            return f"ERRO {e}"


class RobertoListFiles(BaseTool):
    name: str = "listar_workspace"
    description: str = "Lista todos os arquivos no workspace do Roberto."
    def _run(self, **kw) -> str:
        try:
            files = [f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")]
            if not files:
                return "Workspace vazio"
            return "Arquivos:\n" + "\n".join(f"  {f.relative_to(WS_ROBERTO)}" for f in files[:30])
        except Exception as e:
            return f"ERRO {e}"


class RobertoBash(BaseTool):
    name: str = "executar_bash"
    description: str = (
        "Executa um comando bash/shell no workspace do Roberto. "
        "Parametro: command (comando a executar). "
        "Util para: pip install, git, ls, cat, etc."
    )
    def _run(self, command: str = "", **kw) -> str:
        cmd = command or kw.get("cmd", "")
        blocked = ["rm -rf /", "mkfs", "dd if=", ":(){"]
        if any(b in cmd for b in blocked):
            return "ERRO comando bloqueado"
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=str(WS_ROBERTO),
            )
            out = (r.stdout + "\n" + r.stderr).strip()
            return (out or "OK")[:3000]
        except subprocess.TimeoutExpired:
            return "ERRO Timeout"
        except Exception as e:
            return f"ERRO {e}"


# ============================================================
# FERRAMENTAS - CURIOSO
# ============================================================

class CuriosoWebSearch(BaseTool):
    name: str = "buscar_web"
    description: str = (
        "Busca informacoes na internet via DuckDuckGo. "
        "Parametro: query (termo de busca). "
        "Retorna os 5 melhores resultados com titulo, resumo e link."
    )
    def _run(self, query: str = "", **kw) -> str:
        q = query or kw.get("search_query", kw.get("term", ""))
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(q, max_results=5):
                    results.append(f"TITULO: {r['title']}\nRESUMO: {r['body'][:300]}\nLINK: {r['href']}")
            return "\n\n".join(results) if results else "Nenhum resultado"
        except Exception as e:
            return f"ERRO: {e}"


class CuriosoWebFetch(BaseTool):
    name: str = "ler_pagina"
    description: str = (
        "Acessa uma URL e extrai o conteudo de texto da pagina. "
        "Parametro: url (endereco completo com https://). "
        "Util para ler artigos, docs, noticias."
    )
    def _run(self, url: str = "", **kw) -> str:
        u = url or kw.get("page_url", kw.get("link", ""))
        try:
            resp = requests.get(u, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            from html.parser import HTMLParser
            class TE(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.t = []
                    self._s = False
                def handle_starttag(self, tag, a):
                    if tag in ("script", "style", "nav", "footer"):
                        self._s = True
                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer"):
                        self._s = False
                def handle_data(self, d):
                    if not self._s and d.strip():
                        self.t.append(d.strip())
            p = TE()
            p.feed(resp.text)
            return "\n".join(p.t)[:4000]
        except Exception as e:
            return f"ERRO {e}"


class CuriosoSaveResearch(BaseTool):
    name: str = "salvar_pesquisa"
    description: str = (
        "Salva resultado de pesquisa em arquivo no workspace do Curioso. "
        "Parametros: filename (nome do arquivo) e content (conteudo)."
    )
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", f"pesquisa_{datetime.now():%Y%m%d_%H%M}.md")
        ct = content or kw.get("text", "")
        try:
            (WS_CURIOSO / fn).write_text(ct, encoding="utf-8")
            return f"OK salvo: workspace/curioso/{fn}"
        except Exception as e:
            return f"ERRO {e}"


class CuriosoListFiles(BaseTool):
    name: str = "listar_pesquisas"
    description: str = "Lista arquivos salvos no workspace do Curioso."
    def _run(self, **kw) -> str:
        files = [f for f in WS_CURIOSO.rglob("*") if f.is_file()]
        if not files:
            return "Workspace vazio"
        return "Pesquisas:\n" + "\n".join(f"  {f.relative_to(WS_CURIOSO)}" for f in files[:20])


class CuriosoReadFile(BaseTool):
    name: str = "ler_pesquisa"
    description: str = (
        "Le o conteudo de um arquivo do workspace do Curioso. "
        "Parametro: filename."
    )
    def _run(self, filename: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "")
        try:
            path = WS_CURIOSO / fn
            if not path.exists():
                return f"ERRO nao encontrado: {fn}"
            return path.read_text(encoding="utf-8")[:4000]
        except Exception as e:
            return f"ERRO {e}"


# ============================================================
# FERRAMENTAS - MARLEY
# ============================================================

class MarleyGenerateImage(BaseTool):
    name: str = "gerar_imagem"
    description: str = (
        "Gera uma imagem REAL usando IA (Pollinations API, gratis). "
        "Parametro: prompt (descricao DETALHADA da imagem em INGLES, 30-100 palavras). "
        "SEMPRE use esta ferramenta quando pedirem imagem/arte/visual. "
        "Retorna: IMAGE_GENERATED seguido da url e caminho local."
    )
    def _run(self, prompt: str = "", **kw) -> str:
        p = prompt or kw.get("image_prompt", kw.get("description", ""))
        try:
            encoded = requests.utils.quote(p)
            url = f"https://gen.pollinations.ai/image/{encoded}?width=1024&height=1024&nologo=true&enhance=true"
            print(f"[MARLEY] Gerando imagem...")
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code == 200:
                img_data = b""
                for chunk in resp.iter_content(8192):
                    img_data += chunk
                if len(img_data) < 500:
                    return f"ERRO imagem muito pequena ({len(img_data)} bytes)"
                img_name = f"img_{datetime.now():%Y%m%d_%H%M%S}.png"
                img_path = WS_MARLEY / img_name
                img_path.write_bytes(img_data)
                print(f"[MARLEY] Imagem salva: {img_path} ({len(img_data)} bytes)")
                return f"IMAGE_GENERATED url={url} path={img_path} size={len(img_data)}"
            return f"ERRO HTTP {resp.status_code}"
        except requests.Timeout:
            return "ERRO timeout na geracao (tente novamente)"
        except Exception as e:
            return f"ERRO {e}"


class MarleyCreateTemplate(BaseTool):
    name: str = "criar_template"
    description: str = (
        "Cria template HTML/SVG (banner, card, post, logo, mockup). "
        "Parametros: filename (ex: banner.html) e content (codigo HTML/SVG completo)."
    )
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "template.html")
        ct = content or kw.get("html_content", kw.get("code", ""))
        try:
            (WS_MARLEY / fn).write_text(ct, encoding="utf-8")
            return f"OK template: workspace/marley/{fn}"
        except Exception as e:
            return f"ERRO {e}"


class MarleyListFiles(BaseTool):
    name: str = "listar_criacoes"
    description: str = "Lista arquivos no workspace do Marley."
    def _run(self, **kw) -> str:
        files = [f for f in WS_MARLEY.rglob("*") if f.is_file()]
        if not files:
            return "Workspace vazio"
        return "Criacoes:\n" + "\n".join(f"  {f.relative_to(WS_MARLEY)}" for f in files[:20])


class MarleySaveFile(BaseTool):
    name: str = "salvar_arquivo"
    description: str = (
        "Salva qualquer arquivo no workspace do Marley (CSS, JSON, texto, etc). "
        "Parametros: filename e content."
    )
    def _run(self, filename: str = "", content: str = "", **kw) -> str:
        fn = filename or kw.get("file_name", "output.txt")
        ct = content or kw.get("text", "")
        try:
            (WS_MARLEY / fn).write_text(ct, encoding="utf-8")
            return f"OK salvo: workspace/marley/{fn}"
        except Exception as e:
            return f"ERRO {e}"


# ============================================================
# AGENTES
# ============================================================

roberto = Agent(
    role="Roberto - Senior Software Engineer",
    goal=(
        "Entregar projetos de software COMPLETOS e FUNCIONAIS. "
        "NUNCA dar passo-a-passo ou tutorial. "
        "Sempre: 1) Criar TODOS os arquivos usando criar_arquivo, "
        "2) Testar com executar_python, 3) Entregar PRONTO."
    ),
    backstory="""Sou Roberto, engenheiro de software senior com 15+ anos.

MEU METODO:
- Recebo a tarefa e crio TODOS os arquivos no meu workspace
- Testo o codigo executando-o e corrijo se necessario
- Entrego o projeto COMPLETO e FUNCIONAL
- NUNCA dou instrucoes passo-a-passo. EU FACO o trabalho.

FERRAMENTAS DISPONIVEIS:
- criar_arquivo: crio qualquer arquivo (Python, JS, HTML, JSON, YAML, etc)
- executar_python: executo e testo codigo Python
- executar_bash: rodo comandos shell (pip install, git, etc)
- ler_arquivo: leio arquivos existentes
- listar_workspace: vejo meus arquivos

ESPECIALIDADES: Python, APIs, automacao, ETL, web scraping, bots,
arquitetura de sistemas, microservicos, bancos de dados.

Assino: -- Roberto""",
    llm=llm,
    verbose=False,
    allow_delegation=False,
    tools=[
        RobertoCreateFile(),
        RobertoExecuteCode(),
        RobertoReadFile(),
        RobertoListFiles(),
        RobertoBash(),
    ],
)

curioso = Agent(
    role="Curioso - Research Analyst & Intelligence Specialist",
    goal=(
        "Pesquisar na internet usando a ferramenta buscar_web e entregar "
        "APENAS informacoes encontradas na busca real. PROIBIDO inventar dados."
    ),
    backstory="""Sou Curioso, pesquisador com acesso a internet.

REGRA NUMERO 1: Eu SEMPRE uso buscar_web ANTES de responder qualquer pergunta.
REGRA NUMERO 2: Eu NUNCA invento dados, numeros ou fontes.
REGRA NUMERO 3: Se buscar_web nao encontrar, eu digo "nao encontrei dados sobre isso".

MEU PROCESSO OBRIGATORIO:
1. PRIMEIRO: uso buscar_web com termos relevantes
2. SEGUNDO: leio os resultados retornados
3. TERCEIRO: se preciso mais detalhes, uso ler_pagina nos links
4. QUARTO: monto minha resposta APENAS com dados da busca real
5. QUINTO: cito as fontes (links) de onde tirei a informacao

EU NAO TENHO CONHECIMENTO PROPRIO. Tudo que eu sei vem de buscar_web.
Se eu responder sem usar buscar_web, minha resposta esta ERRADA.

Assino: -- Curioso""",
    llm=llm,
    verbose=False,
    allow_delegation=False,
    tools=[
        CuriosoWebSearch(),
        CuriosoWebFetch(),
        CuriosoSaveResearch(),
        CuriosoListFiles(),
        CuriosoReadFile(),
    ],
)

marley = Agent(
    role="Marley - Creative Director & AI Artist",
    goal=(
        "GERAR imagens reais usando a ferramenta gerar_imagem. "
        "NUNCA apenas descrever ou sugerir - SEMPRE gerar usando a ferramenta."
    ),
    backstory="""Sou Marley, artista de IA que GERA imagens de verdade.

REGRA NUMERO 1: Quando pedem imagem, eu SEMPRE uso a ferramenta gerar_imagem.
REGRA NUMERO 2: Eu NUNCA apenas descrevo a imagem. Eu GERO ela.
REGRA NUMERO 3: O prompt para gerar_imagem DEVE ser em INGLES.

MEU PROCESSO OBRIGATORIO PARA IMAGENS:
1. Leio o pedido do usuario
2. Crio um prompt DETALHADO em INGLES (50-100 palavras)
   Incluo: subject, style, lighting, colors, composition, mood, quality keywords
3. Chamo gerar_imagem passando o prompt em ingles
4. Reporto o resultado

EXEMPLO de prompt bom para gerar_imagem:
"A majestic cyberpunk dragon flying over a neon-lit Tokyo cityscape at night,
metallic scales reflecting purple and blue neon lights, dramatic composition,
cinematic lighting, highly detailed, 8k quality, digital art style"

Se eu NAO usar gerar_imagem, minha resposta esta ERRADA e INCOMPLETA.

Para templates HTML/SVG uso criar_template.

Assino: -- Marley""",
    llm=llm,
    verbose=False,
    allow_delegation=False,
    tools=[
        MarleyGenerateImage(),
        MarleyCreateTemplate(),
        MarleyListFiles(),
        MarleySaveFile(),
    ],
)

# ============================================================
# FUNCOES AUXILIARES TELEGRAM
# ============================================================

def split_message(text, max_len=4000):
    text = str(text)
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 <= max_len:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > max_len:
                for i in range(0, len(para), max_len):
                    chunks.append(para[i : i + max_len])
                current = ""
            else:
                current = para + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_len]]


async def send_long(update, text, parse_mode=None):
    for i, chunk in enumerate(split_message(text)):
        try:
            prefix = f"(parte {i + 1})\n\n" if i > 0 else ""
            await update.message.reply_text(prefix + chunk, parse_mode=parse_mode)
        except Exception:
            try:
                await update.message.reply_text(chunk[:4000])
            except Exception:
                pass


async def try_send_image(update, result_text):
    """Tenta extrair imagem do resultado e enviar no Telegram."""
    text = str(result_text)

    # Padrao IMAGE_GENERATED url=... path=...
    match = re.search(r'IMAGE_GENERATED\s+url=(\S+)\s+path=(\S+)', text)
    if match:
        url = match.group(1)
        local_path = match.group(2)
        # Tenta arquivo local
        try:
            if os.path.exists(local_path):
                size = os.path.getsize(local_path)
                if size > 500:
                    with open(local_path, "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption="Imagem gerada por Marley"
                        )
                    return True
        except Exception as ex:
            print(f"[WARN] Falha envio local: {ex}")

        # Fallback: baixa da URL
        try:
            resp = requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 500:
                await update.message.reply_photo(
                    photo=BytesIO(resp.content),
                    caption="Imagem gerada por Marley"
                )
                return True
        except Exception as ex:
            print(f"[WARN] Falha envio URL: {ex}")

        # Ultimo fallback: link
        await update.message.reply_text(f"Imagem gerada:\n{url}")
        return True

    # Busca URLs gen.pollinations.ai soltas no texto
    urls = re.findall(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', text)
    if not urls:
        urls = re.findall(r'https://image\.pollinations\.ai/[^\s\)\"\'<>]+', text)
    for url in urls[:1]:
        try:
            resp = requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 500:
                await update.message.reply_photo(
                    photo=BytesIO(resp.content),
                    caption="Imagem gerada por Marley"
                )
                return True
        except Exception:
            pass
        await update.message.reply_text(f"Imagem:\n{url}")
        return True

    # Verifica se tem arquivo de imagem no workspace do Marley
    imgs = sorted(WS_MARLEY.glob("img_*.png"), reverse=True)
    if imgs:
        latest = imgs[0]
        if latest.stat().st_size > 500:
            age = (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).seconds
            if age < 120:
                try:
                    with open(latest, "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption="Imagem gerada por Marley"
                        )
                    return True
                except Exception:
                    pass

    return False


# ============================================================
# COMANDOS DO BOT
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "IRONCORE AGENTS v3.2\n\n"
        "[ROBERTO] Engenheiro de Software\n"
        "  Cria projetos completos, executa codigo, testa e entrega.\n"
        "  /roberto [tarefa]\n\n"
        "[CURIOSO] Pesquisador & Analista\n"
        "  Pesquisa na web real, analisa dados, entrega insights.\n"
        "  /curioso [pergunta]\n\n"
        "[MARLEY] Diretor Criativo & Artista IA\n"
        "  Gera imagens reais com IA, cria templates e mockups.\n"
        "  /marley [visual]\n\n"
        "[TEAM] Colaboracao Integrada\n"
        "  Os 3 agentes trabalhando juntos.\n"
        "  /team [projeto]\n\n"
        "Outros: /status /workspace /limpar\n\n"
        "Exemplos:\n"
        "  /roberto crie uma API Flask com CRUD de usuarios\n"
        "  /curioso pesquise mercado de FIDCs no Brasil\n"
        "  /marley crie imagem de dragao cyberpunk\n"
        "  /team crie landing page para fintech"
    )


async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /roberto [tarefa]\nEx: /roberto crie script para analise de CSV")
        return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Roberto] Recebeu: {tarefa}\nTrabalhando...")
    task = Task(
        description=(
            f"TAREFA: {tarefa}\n\n"
            "INSTRUCOES OBRIGATORIAS:\n"
            "1. CRIE todos os arquivos necessarios usando criar_arquivo\n"
            "2. TESTE o codigo usando executar_python\n"
            "3. Se der erro, CORRIJA e teste novamente\n"
            "4. Entregue o resultado COMPLETO e FUNCIONAL\n"
            "5. NUNCA de passo-a-passo ou tutorial - FACA o trabalho\n"
            "6. Liste os arquivos criados no final\n"
            "Assine: -- Roberto"
        ),
        agent=roberto,
        expected_output="Projeto completo com todos os arquivos criados e testados",
    )
    crew = Crew(agents=[roberto], tasks=[task], verbose=False)
    try:
        result = str(crew.kickoff())
        await send_long(update, f"[Roberto]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /curioso [pergunta]\nEx: /curioso tendencias de IA generativa 2026")
        return
    pergunta = " ".join(context.args)
    await update.message.reply_text(f"[Curioso] Pesquisando: {pergunta}\nBuscando na web...")
    task = Task(
        description=(
            f"PESQUISA: {pergunta}\n\n"
            "VOCE DEVE OBRIGATORIAMENTE:\n"
            "1. Chamar buscar_web com termos relacionados a pergunta\n"
            "2. Ler os resultados retornados pela busca\n"
            "3. Se necessario, chamar ler_pagina em links relevantes\n"
            "4. Montar sua resposta SOMENTE com informacoes da busca\n"
            "5. Citar os links/fontes de onde veio cada informacao\n\n"
            "PROIBIDO: responder sem ter chamado buscar_web primeiro.\n"
            "PROIBIDO: inventar dados, numeros ou fontes.\n"
            "Se nao encontrar, diga 'nao encontrei dados sobre isso'.\n"
            "Assine: -- Curioso"
        ),
        agent=curioso,
        expected_output="Resposta baseada em dados REAIS de buscar_web com links das fontes",
    )
    crew = Crew(agents=[curioso], tasks=[task], verbose=False)
    try:
        result = str(crew.kickoff())
        await send_long(update, f"[Curioso]\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /marley [visual]\nEx: /marley crie imagem de tigre robotico")
        return
    tarefa = " ".join(context.args)
    await update.message.reply_text(f"[Marley] Criando: {tarefa}\nGerando...")
    task = Task(
        description=(
            f"O usuario pediu: {tarefa}\n\n"
            "VOCE DEVE OBRIGATORIAMENTE:\n"
            "1. Criar um prompt em INGLES (50-100 palavras) descrevendo a imagem\n"
            "   Inclua: subject, style, lighting, colors, composition, mood\n"
            "2. Chamar a ferramenta gerar_imagem passando o prompt em ingles\n"
            "3. Reportar o resultado da geracao\n\n"
            "PROIBIDO: responder sem ter chamado gerar_imagem.\n"
            "PROIBIDO: apenas descrever a imagem sem gerar.\n"
            "Voce TEM a ferramenta gerar_imagem. USE-A.\n"
            "Assine: -- Marley"
        ),
        agent=marley,
        expected_output="Resultado de gerar_imagem contendo IMAGE_GENERATED",
    )
    crew = Crew(agents=[marley], tasks=[task], verbose=False)
    try:
        result = str(crew.kickoff())
        sent = await try_send_image(update, result)
        clean = result
        if sent:
            clean = re.sub(r'IMAGE_GENERATED\s+url=\S+\s+path=\S+\s+size=\d+', '[imagem enviada acima]', clean)
            clean = re.sub(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', '[imagem enviada]', clean)
            clean = re.sub(r'https://image\.pollinations\.ai/[^\s\)\"\'<>]+', '[imagem enviada]', clean)
        await send_long(update, f"[Marley]\n\n{clean}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /team [projeto]\nEx: /team criar landing page fintech")
        return
    projeto = " ".join(context.args)
    await update.message.reply_text(f"[Team] Projeto: {projeto}\n3 agentes trabalhando...")

    task_r = Task(
        description=(
            f"PROJETO: {projeto}\n"
            "Voce e o ENGENHEIRO. Sua parte:\n"
            "1. Arquitetura tecnica e implementacao\n"
            "2. Crie os arquivos de codigo usando criar_arquivo\n"
            "3. Teste o que criou\n"
            "Assine: -- Roberto"
        ),
        agent=roberto,
        expected_output="Parte tecnica implementada",
    )
    task_c = Task(
        description=(
            f"PROJETO: {projeto}\n"
            "Voce e o PESQUISADOR. Sua parte:\n"
            "1. Use buscar_web para pesquisar mercado e tendencias\n"
            "2. Forneca dados e insights para embasar o projeto\n"
            "3. Salve a pesquisa se relevante\n"
            "Assine: -- Curioso"
        ),
        agent=curioso,
        expected_output="Pesquisa de mercado e insights",
    )
    task_m = Task(
        description=(
            f"PROJETO: {projeto}\n"
            "Voce e o DIRETOR CRIATIVO. Sua parte:\n"
            "1. Identidade visual do projeto\n"
            "2. Use gerar_imagem para criar visual (logo, banner, etc)\n"
            "3. Use criar_template para mockups HTML se aplicavel\n"
            "Assine: -- Marley"
        ),
        agent=marley,
        expected_output="Visual e identidade criativa",
    )

    crew = Crew(
        agents=[roberto, curioso, marley],
        tasks=[task_r, task_c, task_m],
        verbose=False,
    )
    try:
        result = str(crew.kickoff())
        sent = await try_send_image(update, result)
        clean = result
        if sent:
            clean = re.sub(r'IMAGE_GENERATED\s+url=\S+\s+path=\S+\s+size=\d+', '[imagem enviada]', clean)
            clean = re.sub(r'https://gen\.pollinations\.ai/image/[^\s\)\"\'<>]+', '[imagem enviada]', clean)
        await send_long(update, f"[Team]\n\n{clean}")
    except Exception as e:
        await update.message.reply_text(f"Erro: {str(e)[:500]}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r_files = len([f for f in WS_ROBERTO.rglob("*") if f.is_file() and not f.name.startswith("_")])
    c_files = len([f for f in WS_CURIOSO.rglob("*") if f.is_file()])
    m_files = len([f for f in WS_MARLEY.rglob("*") if f.is_file()])
    await update.message.reply_text(
        f"IRONCORE AGENTS v3.2 - {datetime.now().strftime('%d/%m %H:%M')}\n\n"
        f"[Roberto] ONLINE\n"
        f"  Workspace: {r_files} arquivo(s)\n"
        f"  Tools: criar_arquivo, executar_python, executar_bash, ler_arquivo, listar_workspace\n\n"
        f"[Curioso] ONLINE\n"
        f"  Workspace: {c_files} arquivo(s)\n"
        f"  Tools: buscar_web, ler_pagina, salvar_pesquisa, listar_pesquisas, ler_pesquisa\n\n"
        f"[Marley] ONLINE\n"
        f"  Workspace: {m_files} arquivo(s)\n"
        f"  Tools: gerar_imagem, criar_template, salvar_arquivo, listar_criacoes\n\n"
        f"Todos operacionais"
    )


async def cmd_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "WORKSPACES\n\n"
    for name, ws in [("Roberto", WS_ROBERTO), ("Curioso", WS_CURIOSO), ("Marley", WS_MARLEY)]:
        files = [f for f in ws.rglob("*") if f.is_file() and not f.name.startswith("_")]
        msg += f"{'=' * 30}\n{name}\n"
        if files:
            for f in files[:10]:
                size = f.stat().st_size
                msg += f"  {f.relative_to(ws)} ({size:,}b)\n"
            if len(files) > 10:
                msg += f"  ... +{len(files) - 10} arquivos\n"
        else:
            msg += "  (vazio)\n"
        msg += "\n"
    await update.message.reply_text(msg)


async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = 0
    for ws in (WS_ROBERTO, WS_CURIOSO, WS_MARLEY):
        for f in ws.rglob("*"):
            if f.is_file():
                f.unlink()
                count += 1
    await update.message.reply_text(f"{count} arquivo(s) removido(s) dos workspaces.")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("IRONCORE AGENTS v3.2")
    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 50)
    print()
    print(f"Roberto - Engenheiro | Workspace: {WS_ROBERTO}")
    print(f"  Tools: criar_arquivo, executar_python, executar_bash, ler_arquivo, listar_workspace")
    print()
    print(f"Curioso - Pesquisador | Workspace: {WS_CURIOSO}")
    print(f"  Tools: buscar_web, ler_pagina, salvar_pesquisa, listar_pesquisas, ler_pesquisa")
    print()
    print(f"Marley - Criativo | Workspace: {WS_MARLEY}")
    print(f"  Tools: gerar_imagem, criar_template, salvar_arquivo, listar_criacoes")
    print()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("roberto", cmd_roberto))
    app.add_handler(CommandHandler("curioso", cmd_curioso))
    app.add_handler(CommandHandler("marley", cmd_marley))
    app.add_handler(CommandHandler("team", cmd_team))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("workspace", cmd_workspace))
    app.add_handler(CommandHandler("limpar", cmd_limpar))

    print("Bot configurado!")
    print("Aguardando comandos no Telegram...\n")

    app.run_polling()


if __name__ == "__main__":
    main()
