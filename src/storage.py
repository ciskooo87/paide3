"""
IRIS - Storage Layer (SQLite)
Substitui load_data/save_data por persistência estruturada
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

# Caminho do banco
DB_PATH = Path(__file__).parent.parent / "data" / "iris.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    """Context manager para conexão SQLite"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Inicializa o banco de dados com o schema"""
    schema_path = Path(__file__).parent.parent / "iris_schema.sql"
    
    with get_db() as conn:
        if schema_path.exists():
            conn.executescript(schema_path.read_text(encoding="utf-8"))
        else:
            # Schema inline caso o arquivo não exista
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_conversation_timestamp ON conversation_history(timestamp DESC);
                
                CREATE TABLE IF NOT EXISTS diary_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    texto TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_diary_date ON diary_entries(date DESC);
                
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texto TEXT NOT NULL,
                    feita BOOLEAN DEFAULT 0,
                    criada_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                    feita_em DATETIME
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_feita ON tasks(feita, criada_em DESC);
                
                CREATE TABLE IF NOT EXISTS mood_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    nivel INTEGER NOT NULL,
                    nota TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_mood_date ON mood_entries(date DESC);
                
                CREATE TABLE IF NOT EXISTS workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date DESC);
                
                CREATE TABLE IF NOT EXISTS pomodoros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    tarefa TEXT NOT NULL,
                    minutos INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_pomodoros_date ON pomodoros(date DESC);
                
                CREATE TABLE IF NOT EXISTS weekly_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    semana TEXT NOT NULL,
                    texto TEXT NOT NULL,
                    concluida BOOLEAN DEFAULT 0,
                    criada_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                    concluida_em DATETIME
                );
                CREATE INDEX IF NOT EXISTS idx_weekly_goals_semana ON weekly_goals(semana DESC);
                
                CREATE TABLE IF NOT EXISTS night_thoughts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    texto TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_night_thoughts_date ON night_thoughts(date DESC);
                
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    hora TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    ativo BOOLEAN DEFAULT 1,
                    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_reminders_ativo ON reminders(ativo, hora);
            """)


# ============================================================
# CONVERSATION HISTORY
# ============================================================

def add_to_history(role: str, content: str):
    """Adiciona mensagem ao histórico"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversation_history (role, content) VALUES (?, ?)",
            (role, content[:1000])
        )
        # Manter apenas últimas 30 mensagens
        conn.execute("""
            DELETE FROM conversation_history 
            WHERE id NOT IN (
                SELECT id FROM conversation_history 
                ORDER BY timestamp DESC LIMIT 30
            )
        """)


def get_history(limit=30):
    """Retorna histórico de conversas"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT role, content, datetime(timestamp, 'localtime') as time
            FROM conversation_history 
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
    
    return [{"role": r["role"], "content": r["content"], "time": r["time"]} 
            for r in reversed(rows)]


# ============================================================
# DIARY
# ============================================================

def add_diary_entry(date: str, texto: str):
    """Adiciona entrada no diário"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO diary_entries (date, texto) VALUES (?, ?)",
            (date, texto)
        )


def get_diary_entries(date: str):
    """Retorna entradas do diário de uma data"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT texto, datetime(timestamp, 'localtime') as time FROM diary_entries WHERE date = ? ORDER BY timestamp",
            (date,)
        ).fetchall()
    
    return [{"texto": r["texto"], "time": r["time"]} for r in rows]


# ============================================================
# TASKS
# ============================================================

def add_task(texto: str):
    """Adiciona nova tarefa"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (texto) VALUES (?)",
            (texto,)
        )
        return cursor.lastrowid


def get_tasks(only_pending=False):
    """Retorna lista de tarefas"""
    with get_db() as conn:
        query = "SELECT * FROM tasks"
        if only_pending:
            query += " WHERE feita = 0"
        query += " ORDER BY criada_em DESC"
        
        rows = conn.execute(query).fetchall()
    
    return [{
        "id": r["id"],
        "texto": r["texto"],
        "feita": bool(r["feita"]),
        "criada_em": r["criada_em"],
        "feita_em": r["feita_em"]
    } for r in rows]


def complete_task(task_id: int):
    """Marca tarefa como concluída"""
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET feita = 1, feita_em = ? WHERE id = ?",
            (datetime.now().isoformat(), task_id)
        )


# ============================================================
# MOOD
# ============================================================

def add_mood(date: str, nivel: int, nota: str = ""):
    """Registra humor"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO mood_entries (date, nivel, nota) VALUES (?, ?, ?)",
            (date, nivel, nota)
        )


def get_mood(date: str):
    """Retorna registros de humor de uma data"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT nivel, nota FROM mood_entries WHERE date = ? ORDER BY timestamp",
            (date,)
        ).fetchall()
    
    return [{"nivel": r["nivel"], "nota": r["nota"] or ""} for r in rows]


# ============================================================
# WORKOUTS
# ============================================================

def add_workout(date: str, tipo: str):
    """Registra treino"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO workouts (date, tipo) VALUES (?, ?)",
            (date, tipo)
        )


def get_workouts(date: str):
    """Retorna treinos de uma data"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tipo FROM workouts WHERE date = ? ORDER BY timestamp",
            (date,)
        ).fetchall()
    
    return [{"tipo": r["tipo"]} for r in rows]


# ============================================================
# POMODOROS
# ============================================================

def add_pomodoro(date: str, tarefa: str, minutos: int):
    """Registra pomodoro"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO pomodoros (date, tarefa, minutos) VALUES (?, ?, ?)",
            (date, tarefa, minutos)
        )


def get_pomodoros(date: str):
    """Retorna pomodoros de uma data"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tarefa, minutos FROM pomodoros WHERE date = ? ORDER BY timestamp",
            (date,)
        ).fetchall()
    
    return [{"tarefa": r["tarefa"], "minutos": r["minutos"]} for r in rows]


# ============================================================
# WEEKLY GOALS
# ============================================================

def add_weekly_goal(semana: str, texto: str):
    """Adiciona meta semanal"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO weekly_goals (semana, texto) VALUES (?, ?)",
            (semana, texto)
        )
        return cursor.lastrowid


def get_weekly_goals(semana: str):
    """Retorna metas de uma semana"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, texto, concluida FROM weekly_goals WHERE semana = ? ORDER BY criada_em",
            (semana,)
        ).fetchall()
    
    return [{
        "id": r["id"],
        "texto": r["texto"],
        "concluida": bool(r["concluida"])
    } for r in rows]


def complete_weekly_goal(goal_id: int):
    """Marca meta como concluída"""
    with get_db() as conn:
        conn.execute(
            "UPDATE weekly_goals SET concluida = 1, concluida_em = ? WHERE id = ?",
            (datetime.now().isoformat(), goal_id)
        )


# ============================================================
# NIGHT THOUGHTS
# ============================================================

def save_night_thought(date: str, texto: str):
    """Salva pensamento noturno"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO night_thoughts (date, texto) VALUES (?, ?)",
            (date, texto)
        )


def get_last_night_thought():
    """Retorna último pensamento noturno"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT date, texto FROM night_thoughts ORDER BY date DESC LIMIT 1"
        ).fetchone()
    
    if row:
        return {"data": row["date"], "ultimo": row["texto"]}
    return {"data": None, "ultimo": "Nenhum"}


def get_night_thoughts_history(limit=30):
    """Retorna histórico de pensamentos noturnos"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT date, texto FROM night_thoughts ORDER BY date DESC LIMIT ?",
            (limit,)
        ).fetchall()
    
    return [{"data": r["date"], "texto": r["texto"][:500]} for r in rows]


# ============================================================
# REMINDERS
# ============================================================

def add_reminder(tipo: str, hora: str, chat_id: str):
    """Adiciona lembrete"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO reminders (tipo, hora, chat_id) VALUES (?, ?, ?)",
            (tipo, hora, chat_id)
        )


def get_active_reminders():
    """Retorna lembretes ativos"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tipo, hora, chat_id FROM reminders WHERE ativo = 1 ORDER BY hora"
        ).fetchall()
    
    return [{"tipo": r["tipo"], "hora": r["hora"], "chat_id": r["chat_id"]} for r in rows]


def clear_reminders():
    """Desativa todos os lembretes"""
    with get_db() as conn:
        conn.execute("UPDATE reminders SET ativo = 0")


# Inicializa o banco ao importar o módulo
init_db()
