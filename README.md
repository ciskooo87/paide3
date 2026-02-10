# IRONCORE AGENTS v3.0

Time de Agentes IA para Telegram com workspaces independentes.

## Agentes

- **👷 Roberto** — Engenheiro de Software (cria, testa e entrega código)
- **🔬 Curioso** — Pesquisador & Analista (busca web real, análise profunda)
- **🎨 Marley** — Diretor Criativo (gera imagens reais com IA, templates)

## Comandos

| Comando | Agente | Exemplo |
|---------|--------|---------|
| `/roberto [tarefa]` | Engenheiro | `/roberto crie API Flask CRUD` |
| `/curioso [pergunta]` | Pesquisador | `/curioso mercado FIDCs Brasil` |
| `/marley [visual]` | Criativo | `/marley dragão cyberpunk` |
| `/team [projeto]` | Todos | `/team landing page fintech` |
| `/status` | — | Ver status dos agentes |
| `/workspace` | — | Ver arquivos dos workspaces |
| `/limpar` | — | Limpar todos os workspaces |

## Deploy (Render.com)

1. Crie Background Worker
2. Conecte este repositório
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python src/bot.py`
5. Variáveis: `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
