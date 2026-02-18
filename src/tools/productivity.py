# -*- coding: utf-8 -*-
"""
IRIS - Productivity Tools
Tarefas, metas, diário, humor, exercícios, dashboard
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Adicionar src ao path para importar storage
sys.path.append(str(Path(__file__).parent.parent))
import storage
from config import BRT

# ============================================================
# HELPERS
# ============================================================

def today_str():
    return datetime.now(BRT).strftime("%Y-%m-%d")

def now_str():
    return datetime.now(BRT).strftime("%Y-%m-%d %H:%M")

def week_key():
    d = datetime.now(BRT)
    return (d - timedelta(days=d.weekday())).strftime("%Y-W%W")


# ============================================================
# TASKS
# ============================================================

def fn_add_task(texto):
    """Adiciona nova tarefa."""
    task_id = storage.add_task(texto)
    return f"Tarefa #{task_id}: {texto}"


def fn_list_tasks():
    """Lista tarefas pendentes e concluídas hoje."""
    tasks = storage.get_tasks()
    pend = [t for t in tasks if not t["feita"]]
    feitas = [t for t in tasks if t["feita"] and (t.get("feita_em") or "").startswith(today_str())]
    
    msg = ""
    if pend:
        msg += "PENDENTES:\n" + "\n".join(f"  #{t['id']} {t['texto']}" for t in pend)
    if feitas:
        msg += f"\nHOJE ({len(feitas)}):\n" + "\n".join(f"  #{t['id']} {t['texto']}" for t in feitas)
    
    return msg or "Nenhuma tarefa."


def fn_complete_task(task_id):
    """Marca tarefa como concluída."""
    tasks = storage.get_tasks()
    for t in tasks:
        if t["id"] == task_id and not t["feita"]:
            storage.complete_task(task_id)
            return f"#{task_id} concluida: {t['texto']}"
    return f"#{task_id} nao encontrada."


# ============================================================
# GOALS
# ============================================================

def fn_add_goal(texto):
    """Adiciona meta semanal."""
    wk = week_key()
    storage.add_weekly_goal(wk, texto)
    return f"Meta semanal: {texto}"


def fn_list_goals():
    """Lista metas da semana."""
    wk = week_key()
    metas = storage.get_weekly_goals(wk)
    
    if not metas:
        return "Sem metas esta semana."
    
    return "\n".join(
        f"  {i}. [{'OK' if m['concluida'] else '...'}] {m['texto']}"
        for i, m in enumerate(metas, 1)
    )


# ============================================================
# JOURNAL
# ============================================================

def fn_add_journal(texto):
    """Adiciona entrada no diário."""
    hoje = today_str()
    storage.add_diary_entry(hoje, texto)
    entries = storage.get_diary_entries(hoje)
    return f"Diario registrado ({len(entries)}a entrada)"


def fn_view_journal():
    """Mostra diário de hoje."""
    hoje = today_str()
    entries = storage.get_diary_entries(hoje)
    
    if not entries:
        return "Diario vazio hoje."
    
    return "\n".join(
        f"[{e.get('time', e.get('hora', ''))}] {e['texto']}"
        for e in entries
    )


# ============================================================
# HEALTH
# ============================================================

def fn_log_exercise(tipo):
    """Registra exercício/treino."""
    hoje = today_str()
    storage.add_workout(hoje, tipo)
    
    # Contar treinos da semana
    wk = 0
    for i in range(7):
        data_dia = (datetime.now(BRT) - timedelta(days=i)).strftime("%Y-%m-%d")
        wk += len(storage.get_workouts(data_dia))
    
    return f"Treino: {tipo}. Semana: {wk} sessao(es)"


def fn_log_mood(nivel, nota=""):
    """Registra humor de 1 (péssimo) a 5 (ótimo)."""
    hoje = today_str()
    storage.add_mood(hoje, nivel, nota)
    
    labels = ["", "pessimo", "ruim", "neutro", "bom", "otimo"]
    return f"Humor: {nivel}/5 ({labels[nivel]}) {nota}"


# ============================================================
# DASHBOARD
# ============================================================

def fn_dashboard():
    """Dashboard completo do dia."""
    hoje = today_str()
    
    diario = storage.get_diary_entries(hoje)
    tarefas = storage.get_tasks()
    pend = [t for t in tarefas if not t["feita"]]
    feitas = [t for t in tarefas if t["feita"] and (t.get("feita_em") or "").startswith(hoje)]
    pomos = storage.get_pomodoros(hoje)
    treinos = storage.get_workouts(hoje)
    humor = storage.get_mood(hoje)
    metas = storage.get_weekly_goals(week_key())
    
    msg = f"DASHBOARD {hoje}\n"
    msg += f"Diario: {len(diario)} entradas\n"
    msg += f"Tarefas: {len(feitas)} feitas / {len(pend)} pendentes\n"
    
    if pend:
        msg += "".join(f"  #{t['id']} {t['texto'][:40]}\n" for t in pend[:5])
    
    msg += f"Pomodoros: {len(pomos)}\n"
    msg += f"Treino: {len(treinos)}\n"
    
    if humor:
        msg += f"Humor: {humor[-1]['nivel']}/5 {humor[-1].get('nota','')}\n"
    
    if metas:
        ok = sum(1 for m in metas if m["concluida"])
        msg += f"Metas: {ok}/{len(metas)}\n"
    
    return msg


def fn_briefing():
    """Briefing matinal completo."""
    from .web import fn_web_news, fn_reddit
    from .email_tool import fn_read_emails
    from .github import fn_github_activity
    from config import GMAIL_EMAIL, GITHUB_TOKEN
    
    # Notícias
    news = ""
    for q in ["Brasil economia hoje", "AI technology news 2026", "world news today"]:
        news += fn_web_news(q, 3) + "\n"
    
    # Reddit
    reddit = fn_reddit("technology", 5)
    
    # Emails
    email_txt = fn_read_emails("gmail", 5) if GMAIL_EMAIL else "(nao configurado)"
    
    # Tarefas e metas
    tasks = fn_list_tasks()
    goals = fn_list_goals()
    
    # Pensamento noturno
    pensamentos = storage.get_last_night_thought()
    ultimo = pensamentos.get("ultimo", "")
    
    # GitHub
    gh_activity = fn_github_activity() if GITHUB_TOKEN else "(nao configurado)"
    
    return (
        f"NOTICIAS:\n{news}\n\n"
        f"REDDIT:\n{reddit}\n\n"
        f"EMAILS:\n{email_txt}\n\n"
        f"GITHUB:\n{gh_activity}\n\n"
        f"TAREFAS:\n{tasks}\n\n"
        f"METAS:\n{goals}\n\n"
        f"REFLEXAO NOTURNA:\n{ultimo or '(nenhuma ainda)'}"
    )


def fn_weekly_review():
    """Review da semana com análise."""
    days = [
        (datetime.now(BRT) - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    ]
    
    tarefas = storage.get_tasks()
    metas = storage.get_weekly_goals(week_key())
    
    ctx = ""
    
    # Diário
    for d in days:
        for e in storage.get_diary_entries(d):
            ctx += f"DIARIO {d}: {e['texto'][:150]}\n"
    
    # Tarefas concluídas
    for t in tarefas:
        if t["feita"] and (t.get("feita_em") or "")[:10] in days:
            ctx += f"TAREFA OK: {t['texto']}\n"
    
    ctx += f"PENDENTES: {len([t for t in tarefas if not t['feita']])}\n"
    
    # Pomodoros
    total_pomos = sum(len(storage.get_pomodoros(d)) for d in days)
    ctx += f"POMODOROS: {total_pomos}\n"
    
    # Treinos e humor
    for d in days:
        for t in storage.get_workouts(d):
            ctx += f"TREINO {d}: {t['tipo']}\n"
        for h in storage.get_mood(d):
            ctx += f"HUMOR {d}: {h['nivel']}/5 {h.get('nota','')}\n"
    
    # Metas
    for m in metas:
        ctx += f"META [{'OK' if m['concluida'] else '...'}]: {m['texto']}\n"
    
    return ctx
