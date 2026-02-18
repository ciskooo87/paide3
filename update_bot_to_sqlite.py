"""
IRIS - Atualização Automática bot.py para SQLite
Substitui chamadas JSON por storage.py de forma segura
"""

import re
import shutil
from pathlib import Path
from datetime import datetime

# Caminhos
BOT_FILE = Path("src/bot.py")
BACKUP_FILE = Path(f"src/bot.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

def update_bot_py():
    """Atualiza bot.py para usar storage.py"""
    
    if not BOT_FILE.exists():
        print("❌ Arquivo bot.py não encontrado!")
        return False
    
    print("="*60)
    print("IRIS - ATUALIZAÇÃO BOT.PY → SQLite")
    print("="*60)
    
    # 1. Fazer backup
    print(f"\n[1/5] Criando backup: {BACKUP_FILE.name}...")
    shutil.copy(BOT_FILE, BACKUP_FILE)
    print(f"  ✓ Backup criado")
    
    # 2. Ler arquivo
    print("\n[2/5] Lendo bot.py...")
    content = BOT_FILE.read_text(encoding="utf-8")
    original_lines = len(content.split('\n'))
    print(f"  ✓ {original_lines} linhas lidas")
    
    # 3. Adicionar imports
    print("\n[3/5] Adicionando imports do storage...")
    
    # Procurar onde adicionar o import (após outros imports)
    import_pattern = r'(from pathlib import Path.*?\n)'
    if re.search(import_pattern, content):
        content = re.sub(
            import_pattern,
            r'\1\n# Storage SQLite\nimport sys\nsys.path.append("src")\nimport storage\n',
            content,
            count=1
        )
        print("  ✓ Imports adicionados após 'from pathlib import Path'")
    else:
        # Se não achar, adicionar no início após os imports padrão
        content = re.sub(
            r'(import os\n)',
            r'\1\n# Storage SQLite\nimport sys\nsys.path.append("src")\nimport storage\n',
            content,
            count=1
        )
        print("  ✓ Imports adicionados após 'import os'")
    
    # 4. Remover funções antigas
    print("\n[4/5] Removendo funções antigas load_data/save_data...")
    
    # Remover load_data
    content = re.sub(
        r'def load_data\(name\):.*?(?=\ndef |$)',
        '',
        content,
        flags=re.DOTALL
    )
    
    # Remover save_data
    content = re.sub(
        r'def save_data\(name, data\):.*?(?=\ndef |$)',
        '',
        content,
        flags=re.DOTALL
    )
    
    print("  ✓ Funções antigas removidas")
    
    # 5. Substituir chamadas
    print("\n[5/5] Substituindo chamadas...")
    
    substituicoes = {
        # Conversation history
        r'add_to_history\(': 'storage.add_to_history(',
        r'get_history\(\)': 'storage.get_history()',
        
        # Tasks  
        r'load_data\("tarefas"\)': 'storage.get_tasks()',
        r'save_data\("tarefas"': 'storage.add_task',  # Precisa ajuste manual depois
        
        # Diary
        r'load_data\("diario"\)': 'storage.get_diary_entries',
        r'save_data\("diario"': 'storage.add_diary_entry',
        
        # Mood
        r'load_data\("humor"\)': 'storage.get_mood',
        r'save_data\("humor"': 'storage.add_mood',
        
        # Workouts
        r'load_data\("treinos"\)': 'storage.get_workouts',
        r'save_data\("treinos"': 'storage.add_workout',
        
        # Pomodoros
        r'load_data\("pomodoros"\)': 'storage.get_pomodoros',
        r'save_data\("pomodoros"': 'storage.add_pomodoro',
        
        # Weekly goals
        r'load_data\("metas"\)': 'storage.get_weekly_goals',
        r'save_data\("metas"': 'storage.add_weekly_goal',
        
        # Night thoughts
        r'load_data\("pensamentos_noturnos"\)': 'storage.get_last_night_thought()',
        r'save_data\("pensamentos_noturnos"': 'storage.save_night_thought',
        
        # Reminders
        r'load_data\("lembretes"\)': 'storage.get_active_reminders()',
        r'save_data\("lembretes"': 'storage.add_reminder',
    }
    
    count = 0
    for old, new in substituicoes.items():
        matches = len(re.findall(old, content))
        if matches > 0:
            content = re.sub(old, new, content)
            count += matches
            print(f"  ✓ {matches}x: {old[:30]}... → {new[:30]}...")
    
    print(f"\n  Total: {count} substituições realizadas")
    
    # 6. Salvar arquivo atualizado
    print("\n[6/6] Salvando bot.py atualizado...")
    BOT_FILE.write_text(content, encoding="utf-8")
    new_lines = len(content.split('\n'))
    print(f"  ✓ Arquivo salvo ({new_lines} linhas)")
    
    # Resumo
    print("\n" + "="*60)
    print("✅ ATUALIZAÇÃO CONCLUÍDA!")
    print("="*60)
    print(f"\nArquivos:")
    print(f"  Original (backup): {BACKUP_FILE}")
    print(f"  Atualizado: {BOT_FILE}")
    print(f"\nPróximos passos:")
    print(f"  1. Revisar o código (pode haver ajustes manuais)")
    print(f"  2. Testar localmente: python bot.py")
    print(f"  3. Se funcionar: git add . && git commit && git push")
    print(f"  4. Se der erro: restaurar backup")
    
    return True

if __name__ == "__main__":
    try:
        update_bot_py()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        print(f"\nO arquivo original não foi modificado.")
        print(f"Se houver backup, restaure com:")
        print(f"  copy bot.py.backup_* bot.py")
