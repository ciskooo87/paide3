# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from crewai import Agent, Task, Crew, LLM
import re

# Importa tools
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from tools.websearch_tool import WebSearchTool
from tools.imagegen_tool import ImageGeneratorTool

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

WORKSPACE_BASE = "/workspace"
AGENT_WORKSPACES = {
    "roberto": os.path.join(WORKSPACE_BASE, "roberto"),
    "curioso": os.path.join(WORKSPACE_BASE, "curioso"),
    "marley": os.path.join(WORKSPACE_BASE, "marley"),
}

for workspace in AGENT_WORKSPACES.values():
    os.makedirs(workspace, exist_ok=True)

# Instancia tools
search_tool = WebSearchTool()
image_tool = ImageGeneratorTool()

# ==========================================
# AGENTES V2.0 - AUTÔNOMOS E PODEROSOS
# ==========================================

roberto = Agent(
    role="Roberto - Autonomous Software Engineer",
    goal="Desenvolver projetos completos, testá-los e publicar no GitHub",
    backstory=f"""Sou Roberto, desenvolvedor autônomo de software.

MINHAS CAPACIDADES:
- Criar projetos Python completos do zero
- Escrever código limpo e profissional
- Testar e debugar
- Fazer push automático para GitHub
- Entregar projetos 100% funcionais

MINHA ÁREA DE TRABALHO:
{AGENT_WORKSPACES['roberto']}/ - onde crio e testo tudo

WORKFLOW:
1. Entendo o projeto
2. Crio estrutura e código
3. Testo localmente
4. Faço push para GitHub
5. Entrego link do repositório

NÃO FAÇO:
❌ Código incompleto
❌ Projetos pela metade
❌ Explicações longas sem código

FORMATO DE RESPOSTA:
**Projeto:** [nome]
**Repo:** [link GitHub]
**Arquivos:** [lista]
**Como executar:** [comandos]

— Roberto 👷""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

curioso = Agent(
    role="Curioso - Deep Research Analyst",
    goal="Pesquisar PROFUNDAMENTE na web e fornecer dados reais e insights",
    backstory=f"""Sou Curioso, pesquisador com acesso REAL à internet.

MINHAS CAPACIDADES:
- Buscar informações ATUAIS na web
- Analisar múltiplas fontes
- Extrair dados de páginas específicas
- Validar informações
- Fornecer insights acionáveis

COMO TRABALHO:
1. Busco em múltiplas fontes
2. Analiso criticamente os dados
3. Valido informações
4. Sintetizo insights práticos

MINHA ÁREA DE TRABALHO:
{AGENT_WORKSPACES['curioso']}/ - onde organizo pesquisas, notas e fontes

NÃO FAÇO:
❌ Respostas genéricas sem pesquisa
❌ Filosofar sem dados
❌ "Depende do contexto"

FORMATO:
**Pesquisa:** [termo]
**Fontes:** [3-5 fontes]
**Dados:** [informações concretas]
**Insight:** [o que isso significa]

— Curioso 🔬""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

marley = Agent(
    role="Marley - Creative Visual Generator",
    goal="Criar visuais reais: imagens, mockups, logos, designs",
    backstory=f"""Sou Marley, criador visual com IA generativa.

MINHAS CAPACIDADES:
- Gerar imagens REAIS com IA
- Criar logos e identidades visuais
- Mockups de interfaces
- Material visual profissional

COMO TRABALHO:
1. Entendo o conceito
2. Crio prompt otimizado
3. Gero a imagem
4. Entrego o visual pronto

MINHA ÁREA DE TRABALHO:
{AGENT_WORKSPACES['marley']}/ - onde armazeno prompts e versões visuais

NÃO FAÇO:
❌ Só prompts sem imagem
❌ Descrições sem criação
❌ Conceitos sem execução

FORMATO:
**Conceito:** [descrição]
**Imagem:** [entrego a imagem]
**Uso sugerido:** [onde usar]

— Marley 🎨""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# ==========================================
# COMANDOS
# ==========================================

def split_message(text, max_length=4000):
    if len(text) <= max_length:
        return [text]
    chunks = []
    current = ""
    for para in text.split('\n\n'):
        if len(current) + len(para) + 2 <= max_length:
            current += para + '\n\n'
        else:
            if current:
                chunks.append(current.strip())
            current = para + '\n\n'
    if current:
        chunks.append(current.strip())
    return chunks

async def send_long_message(update, text):
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        if i == 0:
            await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(f"(parte {i+1})\n\n{chunk}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"""🤖 Time de Agentes IA V2.0 - AUTÔNOMOS

👷 ROBERTO - Desenvolvedor
   ✓ Cria projetos completos
   ✓ Testa e publica no GitHub
   ✓ Workspace: {AGENT_WORKSPACES['roberto']}

🔬 CURIOSO - Pesquisador
   ✓ Acesso real à internet
   ✓ Pesquisa profunda
   ✓ Dados e insights
   ✓ Workspace: {AGENT_WORKSPACES['curioso']}

🎨 MARLEY - Criador Visual
   ✓ Gera imagens reais
   ✓ Logos e mockups
   ✓ Material visual
   ✓ Workspace: {AGENT_WORKSPACES['marley']}

Comandos:
/roberto [projeto] - Cria e publica
/curioso [pesquisa] - Busca na web
/marley [visual] - Cria imagem
/team [projeto completo]
/status
"""
    await update.message.reply_text(msg)

async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /roberto [descrição do projeto]")
        return
    
    projeto = ' '.join(context.args)
    await update.message.reply_text(f"👷 Roberto iniciando: {projeto}\n\n⏳ Criando projeto...")
    
    task = Task(
        description=f"""PROJETO: {projeto}

INSTRUÇÕES:
1. Crie código Python COMPLETO e FUNCIONAL
2. Salve em {AGENT_WORKSPACES['roberto']}/
3. Inclua README.md com instruções
4. Liste todos os arquivos criados
5. Explique como executar

ENTREGA:
- Código completo
- README.md
- Estrutura do projeto
- Como testar

Seja PROFISSIONAL e COMPLETO.

— Roberto 👷""",
        agent=roberto,
        expected_output="Projeto completo"
    )
    
    crew = Crew(agents=[roberto], tasks=[task], verbose=False)
    
    try:
        result = str(crew.kickoff())
        
        # Adiciona info sobre GitHub
        result += f"\n\n📦 **Próximo Passo:**\nUse /github_push para publicar no GitHub!"
        
        await send_long_message(update, f"⚙️ Roberto\n\n{result}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /curioso [sua pesquisa]")
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(f"🔍 Curioso pesquisando: {query}\n\n⏳ Buscando na web...")
    
    # FAZ BUSCA REAL
    search_results = search_tool.search(query, max_results=5)
    
    task = Task(
        description=f"""PESQUISA: {query}

RESULTADOS DA WEB:
{search_results}

WORKSPACE DE PESQUISA:
- Use {AGENT_WORKSPACES['curioso']}/ para organizar notas e fontes durante a análise.

INSTRUÇÕES:
1. Analise os resultados REAIS acima
2. Sintetize as informações
3. Forneça dados CONCRETOS
4. Dê insights práticos

Seja OBJETIVO e baseado em DADOS.

— Curioso 🔬""",
        agent=curioso,
        expected_output="Análise com dados"
    )
    
    crew = Crew(agents=[curioso], tasks=[task], verbose=False)
    
    try:
        result = str(crew.kickoff())
        await send_long_message(update, f"📊 Curioso\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /marley [descrição visual]")
        return
    
    descricao = ' '.join(context.args)
    await update.message.reply_text(f"🎨 Marley criando: {descricao}\n\n⏳ Gerando imagem...")
    
    task = Task(
        description=f"""CRIAR: {descricao}

INSTRUÇÕES:
1. Crie um prompt DETALHADO em inglês (80-120 palavras)
2. Otimize para FLUX/Stable Diffusion
3. Termine com: PROMPT: [seu prompt aqui]
4. Use {AGENT_WORKSPACES['marley']}/ como área de trabalho para rascunhos e variações visuais

— Marley 🎨""",
        agent=marley,
        expected_output="Prompt otimizado"
    )
    
    crew = Crew(agents=[marley], tasks=[task], verbose=False)
    
    try:
        result = str(crew.kickoff())
        
        # Extrai prompt
        match = re.search(r'PROMPT:\s*(.+?)(?:\n\n|$)', result, re.IGNORECASE | re.DOTALL)
        if match:
            prompt = match.group(1).strip()
            
            # GERA IMAGEM REAL
            await update.message.reply_text("⏳ Gerando imagem real (30s)...")
            
            image_data, image_url = image_tool.generate(prompt)
            
            if image_data:
                image_data.name = 'marley.jpg'
                image_data.seek(0)
                await update.message.reply_photo(photo=image_data, caption=f"🎨 Marley\n\n{descricao}")
                await update.message.reply_text(f"✅ Imagem gerada!\n\n📋 Prompt usado:\n{prompt[:200]}...")
            else:
                await update.message.reply_text(f"⚠️ Erro ao gerar imagem.\n\n📋 Prompt criado:\n{prompt}\n\nUse em: DALL-E, Midjourney")
        
        await send_long_message(update, f"🖼️ Marley\n\n{result}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /team [projeto completo]")
        return
    
    projeto = ' '.join(context.args)
    await update.message.reply_text(f"👥 Team: {projeto}\n\n⏳ 60-120s...")
    
    # ROBERTO: Código
    task_r = Task(
        description=f"Roberto: Crie arquitetura técnica para {projeto}. Foque em código Python.",
        agent=roberto,
        expected_output="Arquitetura"
    )
    
    # CURIOSO: Pesquisa
    await update.message.reply_text("🔍 Curioso pesquisando...")
    search_results = search_tool.search(projeto, max_results=3)
    
    task_c = Task(
        description=f"Curioso: Analise mercado de {projeto}.\n\nDados da web:\n{search_results}",
        agent=curioso,
        expected_output="Análise"
    )
    
    # MARLEY: Visual
    task_m = Task(
        description=f"Marley: Crie identidade visual para {projeto}. Faça prompt para logo.",
        agent=marley,
        expected_output="Design"
    )
    
    crew = Crew(agents=[roberto, curioso, marley], tasks=[task_r, task_c, task_m], verbose=False)
    
    try:
        result = str(crew.kickoff())
        await send_long_message(update, f"🎯 Team\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    github_status = "✅" if os.getenv("GITHUB_TOKEN") else "❌"
    replicate_status = "✅" if os.getenv("REPLICATE_API_TOKEN") else "❌"
    
    await update.message.reply_text(f"""✅ {datetime.now().strftime('%d/%m %H:%M')}

👷 Roberto - Online
   GitHub: {github_status}
   Workspace: {AGENT_WORKSPACES['roberto']}

🔬 Curioso - Online
   Web Search: ✅
   Workspace: {AGENT_WORKSPACES['curioso']}

🎨 Marley - Online
   Image Gen: {replicate_status}
   Workspace: {AGENT_WORKSPACES['marley']}

🟢 Time V2.0 operacional
""")

def main():
    print("🚀 Time de Agentes V2.0 - AUTÔNOMOS")
    print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado")

    app = Application.builder().token(bot_token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roberto", cmd_roberto))
    app.add_handler(CommandHandler("curioso", cmd_curioso))
    app.add_handler(CommandHandler("marley", cmd_marley))
    app.add_handler(CommandHandler("team", cmd_team))
    app.add_handler(CommandHandler("status", cmd_status))
    
    print("✅ Time V2.0 configurado!")
    print("⏳ Aguardando no Telegram...\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()
