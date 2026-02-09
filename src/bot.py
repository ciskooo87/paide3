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

roberto = Agent(
    role="Roberto - Senior Software Engineer",
    goal="Desenvolver código Python profissional e resolver problemas técnicos",
    backstory="Sou Roberto, engenheiro sênior com 10+ anos de experiência. Código limpo, soluções práticas. — Roberto 👷",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

curioso = Agent(
    role="Curioso - Research Analyst",
    goal="Analisar dados, pesquisar informações e gerar insights profundos",
    backstory="Sou Curioso, pesquisador e analista. Análise profunda, múltiplas perspectivas, insights acionáveis. — Curioso 🔬",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

marley = Agent(
    role="Marley - AI Image Prompt Master",
    goal="Criar prompts PERFEITOS otimizados para DALL-E, Midjourney, Stable Diffusion",
    backstory="""Sou Marley, mestre em prompts de imagem.

Crio prompts que geram imagens INCRÍVEIS em qualquer plataforma de IA.

FORMATO DA MINHA RESPOSTA:
[1-2 frases sobre o conceito]

###PROMPT###
[Prompt DETALHADO em inglês: 80-150 palavras incluindo sujeito, estilo, composição, iluminação, cores, mood, qualidade técnica]

###ONDE USAR###
- DALL-E 3 (ChatGPT Plus)
- Midjourney (Discord)
- Leonardo.ai (gratuito)
- Stable Diffusion (local)

— Marley 🎨""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

def extract_prompt(text):
    match = re.search(r'###PROMPT###\s*(.+?)(?:###|—|$)', text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback
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
    msg = """🤖 Time de Agentes IA - Online 24/7

👷 ROBERTO - Engenheiro de Software
   • Código Python profissional
   • Scripts e automações
   • Soluções técnicas completas

🔬 CURIOSO - Analista & Pesquisador
   • Análise profunda de dados
   • Pesquisa e insights
   • Recomendações estratégicas

🎨 MARLEY - Prompt Engineer
   • Prompts OTIMIZADOS para IA
   • DALL-E, Midjourney, SD
   • Conceitos visuais profissionais

Comandos:
/roberto [tarefa] - Código e técnica
/curioso [análise] - Pesquisa e insights
/marley [visual] - Prompt para imagem
/team [projeto] - Todos colaboram
/status - Ver status

Exemplos:
/roberto crie código para calcular fibonacci
/curioso analise tendências de IA em 2026
/marley tigre robótico futurista cyberpunk
/team desenvolva dashboard executivo CFO
"""
    await update.message.reply_text(msg)

async def cmd_roberto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /roberto [tarefa]")
        return
    tarefa = ' '.join(context.args)
    await update.message.reply_text(f"👷 Roberto: {tarefa}")
    task = Task(description=f"{tarefa}. Forneça código completo e explicações. — Roberto 👷", agent=roberto, expected_output="Solução")
    crew = Crew(agents=[roberto], tasks=[task], verbose=False)
    try:
        result = crew.kickoff()
        await send_long_message(update, f"⚙️ Roberto\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_curioso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /curioso [análise]")
        return
    tarefa = ' '.join(context.args)
    await update.message.reply_text(f"🔍 Curioso: {tarefa}")
    task = Task(description=f"{tarefa}. Análise profunda com múltiplas perspectivas. — Curioso 🔬", agent=curioso, expected_output="Análise")
    crew = Crew(agents=[curioso], tasks=[task], verbose=False)
    try:
        result = crew.kickoff()
        await send_long_message(update, f"📊 Curioso\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_marley(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /marley [descrição da imagem]")
        return
    
    descricao = ' '.join(context.args)
    await update.message.reply_text(f"🎨 Marley criando prompt: {descricao}")
    
    task = Task(
        description=f"""Crie um prompt PERFEITO para gerar: {descricao}

FORMATO OBRIGATÓRIO:
1-2 frases sobre o conceito

###PROMPT###
[Prompt detalhado 80-150 palavras em INGLÊS incluindo:
- Sujeito principal
- Estilo artístico (photorealistic, digital art, oil painting, etc)
- Composição (close-up, wide shot, aerial view, etc)
- Iluminação (dramatic, soft, neon, golden hour, etc)
- Cores dominantes e mood
- Detalhes técnicos (4K, highly detailed, sharp focus)
- Referências de qualidade (trending on artstation, award winning, masterpiece)]

###ONDE USAR###
Plataformas recomendadas

— Marley 🎨""",
        agent=marley,
        expected_output="Prompt otimizado"
    )
    
    crew = Crew(agents=[marley], tasks=[task], verbose=False)
    
    try:
        result = str(crew.kickoff())
        print(f"\n[MARLEY]\n{result}\n")
        
        prompt = extract_prompt(result)
        
        if prompt:
            # Monta resposta formatada
            response = f"""🎨 **MARLEY - Prompt Pronto!**

📋 **COPIE E USE ESTE PROMPT:**
```
{prompt}
```

💡 **Onde usar:**
- DALL-E 3: ChatGPT Plus (chat.openai.com)
- Midjourney: Discord (midjourney.com)
- Leonardo.ai: Gratuito (leonardo.ai)  
- Stable Diffusion: Local ou online

🔥 **Dica:** Copie o texto acima e cole direto na plataforma de sua escolha!

---
Resposta completa:

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
    tarefa = ' '.join(context.args)
    await update.message.reply_text(f"👥 Team: {tarefa}\n⏳ 30-90s...")
    
    task_r = Task(description=f"Roberto: aspectos técnicos de {tarefa}", agent=roberto, expected_output="Análise técnica")
    task_c = Task(description=f"Curioso: pesquise e analise {tarefa}", agent=curioso, expected_output="Insights")
    task_m = Task(description=f"Marley: conceito visual para {tarefa}", agent=marley, expected_output="Conceito")
    
    crew = Crew(agents=[roberto, curioso, marley], tasks=[task_r, task_c, task_m], verbose=False)
    
    try:
        result = str(crew.kickoff())
        await send_long_message(update, f"🎯 Team Collaboration\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""✅ Status - {datetime.now().strftime('%d/%m/%Y %H:%M')}

👷 Roberto - Online
   Especialidade: Python, automação, arquitetura

🔬 Curioso - Online
   Especialidade: Análise, pesquisa, insights

🎨 Marley - Online
   Especialidade: Prompts IA otimizados

🟢 Todos agentes operacionais
""")

def main():
    print("🚀 Time de Agentes IA")
    print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    print("👷 Roberto - Engenheiro")
    print("🔬 Curioso - Analista")
    print("🎨 Marley - Prompt Master")
    
    app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roberto", cmd_roberto))
    app.add_handler(CommandHandler("curioso", cmd_curioso))
    app.add_handler(CommandHandler("marley", cmd_marley))
    app.add_handler(CommandHandler("team", cmd_team))
    app.add_handler(CommandHandler("status", cmd_status))
    
    print("\n✅ Configurado!")
    print("⏳ Aguardando no Telegram...\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()