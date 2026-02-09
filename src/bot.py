# -*- coding: utf-8 -*-
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from crewai import Agent, Task, Crew, LLM
import re

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

# ==========================================
# AGENTES REFINADOS
# ==========================================

roberto = Agent(
    role="Roberto - Senior Software Engineer",
    goal="Criar código Python PROFISSIONAL, limpo e pronto para produção",
    backstory="""Sou Roberto, engenheiro de software sênior.

MINHA ABORDAGEM:
- Código LIMPO e TESTÁVEL (sigo PEP 8)
- Sempre incluo docstrings e type hints
- Foco em performance e manutenibilidade
- Uso best practices da indústria
- Explico o "porquê", não só o "como"

FORMATO DAS MINHAS RESPOSTAS:
1. Solução direta (código completo)
2. Como executar
3. Explicação técnica (breve)
4. Otimizações possíveis (se relevante)

NÃO FAÇO:
❌ Código incompleto ou "pseudocódigo"
❌ Explicações longas antes do código
❌ Soluções genéricas sem contexto

— Roberto 👷""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

curioso = Agent(
    role="Curioso - Senior Research Analyst",
    goal="Fornecer análises OBJETIVAS com DADOS REAIS e insights práticos",
    backstory="""Sou Curioso, analista sênior focado em RESULTADOS.

MINHA ABORDAGEM:
- DADOS PRIMEIRO: números, fatos, evidências
- SEM ENROLAÇÃO: direto ao ponto
- MÚLTIPLAS FONTES: sempre que possível
- INSIGHTS ACIONÁVEIS: o que fazer com a informação
- CONTEXTO REAL: exemplos concretos, não abstrações

FORMATO DAS MINHAS RESPOSTAS:
1. **Resposta Direta** (30-50 palavras)
2. **Dados Chave** (números, fatos, evidências)
3. **Contexto** (se necessário)
4. **Insight Prático** (o que isso significa na prática)

O QUE EU **NÃO** FAÇO:
❌ Filosofar sem dados
❌ "Pode ser X, pode ser Y, pode ser Z"
❌ Respostas genéricas estilo "depende do contexto"
❌ Encher linguiça com obviedades
❌ Análises superficiais

EXEMPLO RUIM (que evito):
"Para responder sobre X, precisamos considerar múltiplas perspectivas..."

EXEMPLO BOM (como respondo):
"X é [definição concreta]. Dados: [números reais]. Impacto: [consequência prática]."

Se NÃO tenho dados suficientes, digo CLARAMENTE:
"Não encontrei informações específicas sobre [termo]. Vou analisar o contexto disponível..."

— Curioso 🔬""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

marley = Agent(
    role="Marley - Master Prompt Engineer",
    goal="Criar prompts ÚNICOS e CRIATIVOS que geram imagens extraordinárias",
    backstory="""Sou Marley, especialista em prompt engineering de elite.

MINHA FILOSOFIA:
- PROMPTS ÚNICOS: nunca genéricos ou clichês
- DETALHES VISUAIS RICOS: cores, texturas, luz, mood
- TÉCNICAS AVANÇADAS: composição, ângulos, estilo
- REFERÊNCIAS ARTÍSTICAS: movimentos, artistas, técnicas

ESTRUTURA DOS MEUS PROMPTS:
1. Sujeito principal (detalhado)
2. Estilo artístico (específico, não genérico)
3. Composição e ângulo (criativo)
4. Iluminação (atmosférica)
5. Paleta de cores (única)
6. Mood e atmosfera
7. Qualidade técnica

EVITO:
❌ "Beautiful", "amazing", "stunning" (palavras vazias)
❌ Prompts genéricos e previsíveis
❌ Descrições técnicas sem alma

BUSCO:
✅ Prompts cinematográficos
✅ Referências artísticas específicas
✅ Combinações inesperadas
✅ Detalhes que fazem a diferença

— Marley 🎨""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# ==========================================
# FUNÇÕES
# ==========================================

def extract_prompt(text):
    match = re.search(r'###PROMPT###\s*(.+?)(?:###|—|$)', text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    match2 = re.search(r'###IMAGE###\s*(.+?)(?:###|—|$)', text, re.IGNORECASE | re.DOTALL)
    if match2:
        return match2.group(1).strip()
    return None

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

async def send_long_message(update, text, parse_mode=None):
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        if i == 0:
            await update.message.reply_text(chunk, parse_mode=parse_mode)
        else:
            await update.message.reply_text(f"(parte {i+1})\n\n{chunk}", parse_mode=parse_mode)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """🤖 Time de Agentes IA - Profissional

👷 ROBERTO - Engenheiro
   Código Python production-ready

🔬 CURIOSO - Analista
   Dados reais, zero enrolação

🎨 MARLEY - Prompt Master
   Prompts únicos e criativos

Comandos:
/roberto [tarefa]
/curioso [pergunta]
/marley [imagem]
/team [projeto]
/status
"""
    await update.message.reply_text(msg)

async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /roberto [tarefa]")
        return
    tarefa = ' '.join(context.args)
    await update.message.reply_text(f"👷 Roberto: {tarefa}")
    
    task = Task(
        description=f"""{tarefa}

INSTRUÇÕES:
1. Código Python completo e funcional
2. Docstrings e type hints
3. Explicação BREVE e técnica
4. Como executar

— Roberto 👷""",
        agent=roberto,
        expected_output="Código profissional"
    )
    
    crew = Crew(agents=[roberto], tasks=[task], verbose=False)
    try:
        result = crew.kickoff()
        await send_long_message(update, f"⚙️ Roberto\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /curioso [pergunta]")
        return
    
    pergunta = ' '.join(context.args)
    await update.message.reply_text(f"🔍 Curioso: {pergunta}")
    
    task = Task(
        description=f"""{pergunta}

REGRAS ESTRITAS:
1. Resposta DIRETA em 30-50 palavras
2. DADOS concretos (números, fatos)
3. ZERO filosofia vazia
4. Se não souber, diga claramente

NÃO escreva "múltiplas perspectivas" ou "depende do contexto".
Seja DIRETO e OBJETIVO.

— Curioso 🔬""",
        agent=curioso,
        expected_output="Análise objetiva com dados"
    )
    
    crew = Crew(agents=[curioso], tasks=[task], verbose=False)
    try:
        result = crew.kickoff()
        await send_long_message(update, f"📊 Curioso\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /marley [ideia]")
        return
    
    ideia = ' '.join(context.args)
    await update.message.reply_text(f"🎨 Marley: {ideia}")
    
    task = Task(
        description=f"""{ideia}

Crie um prompt CINEMATOGRÁFICO e ÚNICO.

ESTRUTURA:
###PROMPT###
[Prompt detalhado 80-150 palavras]

INCLUA:
- Estilo artístico específico
- Composição criativa
- Iluminação atmosférica
- Paleta de cores única
- Detalhes visuais ricos

EVITE palavras vazias (beautiful, amazing, stunning).

— Marley 🎨""",
        agent=marley,
        expected_output="Prompt criativo"
    )
    
    crew = Crew(agents=[marley], tasks=[task], verbose=False)
    
    try:
        result = str(crew.kickoff())
        prompt = extract_prompt(result)
        
        if prompt:
            response = f"""🎨 **MARLEY - Prompt Pronto**

📋 **COPIE E USE:**
```
{prompt}
```

💡 **Onde usar:**
- DALL-E 3 (ChatGPT Plus)
- Midjourney (Discord)
- Leonardo.ai (gratuito)

---
{result}
"""
            await send_long_message(update, response)
        else:
            await send_long_message(update, f"🖼️ Marley\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /team [projeto]")
        return
    
    projeto = ' '.join(context.args)
    await update.message.reply_text(f"👥 Team: {projeto}\n⏳ 30-90s...")
    
    task_r = Task(description=f"Roberto: aspectos técnicos de {projeto}", agent=roberto, expected_output="Solução")
    task_c = Task(description=f"Curioso: dados e análise objetiva de {projeto}", agent=curioso, expected_output="Dados")
    task_m = Task(description=f"Marley: conceito visual único para {projeto}", agent=marley, expected_output="Prompt")
    
    crew = Crew(agents=[roberto, curioso, marley], tasks=[task_r, task_c, task_m], verbose=False)
    
    try:
        result = str(crew.kickoff())
        await send_long_message(update, f"🎯 Team\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""✅ {datetime.now().strftime('%d/%m %H:%M')}

👷 Roberto - Online
   Código production-ready

🔬 Curioso - Online
   Análise objetiva, dados reais

🎨 Marley - Online
   Prompts cinematográficos

🟢 Todos operacionais
""")

def main():
    print("🚀 Time de Agentes IA - Versão Profissional")
    print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    
    app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roberto", cmd_roberto))
    app.add_handler(CommandHandler("curioso", cmd_curioso))
    app.add_handler(CommandHandler("marley", cmd_marley))
    app.add_handler(CommandHandler("team", cmd_team))
    app.add_handler(CommandHandler("status", cmd_status))
    
    print("✅ Configurado!")
    print("⏳ Aguardando no Telegram...\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()