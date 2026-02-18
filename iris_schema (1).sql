-- IRIS - Schema SQLite
-- Database: iris.db
-- Substitui os arquivos JSON por persistência estruturada

-- ============================================================
-- CONVERSAS (historico.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,  -- 'user' ou 'assistant'
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversation_timestamp ON conversation_history(timestamp DESC);

-- ============================================================
-- DIÁRIO (diario.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS diary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    texto TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diary_date ON diary_entries(date DESC);

-- ============================================================
-- TAREFAS (tarefas.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    feita BOOLEAN DEFAULT 0,
    criada_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    feita_em DATETIME
);

CREATE INDEX IF NOT EXISTS idx_tasks_feita ON tasks(feita, criada_em DESC);

-- ============================================================
-- HUMOR (humor.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS mood_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    nivel INTEGER NOT NULL,  -- 1-5
    nota TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mood_date ON mood_entries(date DESC);

-- ============================================================
-- TREINOS (treinos.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    tipo TEXT NOT NULL,  -- 'musculação', 'cardio', etc
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date DESC);

-- ============================================================
-- POMODOROS (pomodoros.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS pomodoros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    tarefa TEXT NOT NULL,
    minutos INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pomodoros_date ON pomodoros(date DESC);

-- ============================================================
-- METAS SEMANAIS (metas.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS weekly_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semana TEXT NOT NULL,  -- 'YYYY-WXX' formato ISO
    texto TEXT NOT NULL,
    concluida BOOLEAN DEFAULT 0,
    criada_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    concluida_em DATETIME
);

CREATE INDEX IF NOT EXISTS idx_weekly_goals_semana ON weekly_goals(semana DESC);

-- ============================================================
-- PENSAMENTOS NOTURNOS (pensamentos_noturnos.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS night_thoughts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    texto TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_night_thoughts_date ON night_thoughts(date DESC);

-- ============================================================
-- LEMBRETES (lembretes.json)
-- ============================================================
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    hora TEXT NOT NULL,  -- 'HH:MM'
    chat_id TEXT NOT NULL,
    ativo BOOLEAN DEFAULT 1,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reminders_ativo ON reminders(ativo, hora);
