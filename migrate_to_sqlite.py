"""
IRIS - Migração JSON → SQLite
Converte dados existentes em JSON para banco SQLite
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Caminhos
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "iris.db"

# Garante que o diretório existe
DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(filename):
    """Carrega arquivo JSON se existir"""
    filepath = DATA_DIR / f"{filename}.json"
    if filepath.exists():
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except:
            return {}
    return {}


def migrate():
    """Executa migração completa"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    print("="*60)
    print("IRIS - MIGRAÇÃO JSON → SQLite")
    print("="*60)
    
    # ============================================================
    # 1. CONVERSATION HISTORY
    # ============================================================
    print("\n[1/9] Migrando histórico de conversas...")
    data = load_json("historico")
    messages = data.get("mensagens", [])
    
    for msg in messages:
        conn.execute(
            "INSERT INTO conversation_history (role, content, timestamp) VALUES (?, ?, ?)",
            (msg["role"], msg["content"][:1000], msg.get("time", datetime.now().isoformat()))
        )
    
    print(f"  ✓ {len(messages)} mensagens migradas")
    
    # ============================================================
    # 2. DIARY
    # ============================================================
    print("\n[2/9] Migrando diário...")
    data = load_json("diario")
    count = 0
    
    for date, entries in data.items():
        if isinstance(entries, list):
            for entry in entries:
                conn.execute(
                    "INSERT INTO diary_entries (date, texto) VALUES (?, ?)",
                    (date, entry.get("texto", ""))
                )
                count += 1
    
    print(f"  ✓ {count} entradas migradas")
    
    # ============================================================
    # 3. TASKS
    # ============================================================
    print("\n[3/9] Migrando tarefas...")
    data = load_json("tarefas")
    tasks = data.get("items", [])
    count = 0
    
    for task in tasks:
        conn.execute(
            "INSERT INTO tasks (id, texto, feita, feita_em) VALUES (?, ?, ?, ?)",
            (task.get("id"), task.get("texto"), 1 if task.get("feita") else 0, task.get("feita_em"))
        )
        count += 1
    
    print(f"  ✓ {count} tarefas migradas")
    
    # ============================================================
    # 4. MOOD
    # ============================================================
    print("\n[4/9] Migrando registros de humor...")
    data = load_json("humor")
    count = 0
    
    for date, entries in data.items():
        if isinstance(entries, list):
            for entry in entries:
                conn.execute(
                    "INSERT INTO mood_entries (date, nivel, nota) VALUES (?, ?, ?)",
                    (date, entry.get("nivel", 3), entry.get("nota", ""))
                )
                count += 1
    
    print(f"  ✓ {count} registros migrados")
    
    # ============================================================
    # 5. WORKOUTS
    # ============================================================
    print("\n[5/9] Migrando treinos...")
    data = load_json("treinos")
    count = 0
    
    for date, workouts in data.items():
        if isinstance(workouts, list):
            for workout in workouts:
                conn.execute(
                    "INSERT INTO workouts (date, tipo) VALUES (?, ?)",
                    (date, workout.get("tipo", "treino"))
                )
                count += 1
    
    print(f"  ✓ {count} treinos migrados")
    
    # ============================================================
    # 6. POMODOROS
    # ============================================================
    print("\n[6/9] Migrando pomodoros...")
    data = load_json("pomodoros")
    count = 0
    
    for date, pomos in data.items():
        if isinstance(pomos, list):
            for pomo in pomos:
                conn.execute(
                    "INSERT INTO pomodoros (date, tarefa, minutos) VALUES (?, ?, ?)",
                    (date, pomo.get("tarefa", ""), pomo.get("minutos", 25))
                )
                count += 1
    
    print(f"  ✓ {count} pomodoros migrados")
    
    # ============================================================
    # 7. WEEKLY GOALS
    # ============================================================
    print("\n[7/9] Migrando metas semanais...")
    data = load_json("metas")
    count = 0
    
    for semana, goals in data.items():
        if isinstance(goals, list):
            for goal in goals:
                conn.execute(
                    "INSERT INTO weekly_goals (semana, texto, concluida) VALUES (?, ?, ?)",
                    (semana, goal.get("texto", ""), 1 if goal.get("concluida") else 0)
                )
                count += 1
    
    print(f"  ✓ {count} metas migradas")
    
    # ============================================================
    # 8. NIGHT THOUGHTS
    # ============================================================
    print("\n[8/9] Migrando pensamentos noturnos...")
    data = load_json("pensamentos_noturnos")
    count = 0
    
    # Último pensamento
    if data.get("ultimo"):
        conn.execute(
            "INSERT INTO night_thoughts (date, texto) VALUES (?, ?)",
            (data.get("data", datetime.now().strftime("%Y-%m-%d")), data["ultimo"])
        )
        count += 1
    
    # Histórico
    for entry in data.get("historico", []):
        if entry.get("texto"):
            conn.execute(
                "INSERT INTO night_thoughts (date, texto) VALUES (?, ?)",
                (entry.get("data", datetime.now().strftime("%Y-%m-%d")), entry["texto"])
            )
            count += 1
    
    print(f"  ✓ {count} pensamentos migrados")
    
    # ============================================================
    # 9. REMINDERS
    # ============================================================
    print("\n[9/9] Migrando lembretes...")
    data = load_json("lembretes")
    reminders = data.get("ativos", [])
    count = 0
    
    for reminder in reminders:
        conn.execute(
            "INSERT INTO reminders (tipo, hora, chat_id) VALUES (?, ?, ?)",
            (reminder.get("tipo"), reminder.get("hora"), str(reminder.get("chat_id")))
        )
        count += 1
    
    print(f"  ✓ {count} lembretes migrados")
    
    # ============================================================
    # FINALIZAR
    # ============================================================
    conn.commit()
    conn.close()
    
    print("\n" + "="*60)
    print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("="*60)
    print(f"\nBanco de dados criado em: {DB_PATH}")
    print("\nPróximos passos:")
    print("1. Faça backup dos arquivos JSON originais")
    print("2. Teste o bot localmente com o novo storage.py")
    print("3. Após confirmar que está funcionando, pode remover os JSONs")


if __name__ == "__main__":
    migrate()
