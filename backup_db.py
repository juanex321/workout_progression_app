"""
Automatic database backup utility.
Creates timestamped backups before any schema changes.
Only works for SQLite databases (local development).
"""
import shutil
from datetime import datetime
from pathlib import Path
from db import DATABASE_URL

# Only backup SQLite databases
DB_PATH = Path("workout.db")
BACKUP_DIR = Path("db_backups")

def create_backup(reason="manual"):
    """
    Create a timestamped backup of the database.
    Only works for SQLite databases.
    
    Args:
        reason: Why the backup is being created (e.g., "migration", "manual")
    
    Returns:
        Path to the backup file
    """
    # Only backup SQLite databases
    if not DATABASE_URL.startswith('sqlite'):
        print(f"⚠️  Backup only works for SQLite databases. Current database: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else DATABASE_URL}")
        return None
    
    if not DB_PATH.exists():
        print(f"⚠️  No database file found at {DB_PATH}")
        return None
    
    BACKUP_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"workout_backup_{timestamp}_{reason}.db"
    
    shutil.copy2(DB_PATH, backup_path)
    
    print(f"✅ Database backed up to: {backup_path}")
    return backup_path

def list_backups():
    """List all available backups."""
    if not BACKUP_DIR.exists():
        print("No backups directory found.")
        return []
    
    backups = sorted(BACKUP_DIR.glob("workout_backup_*.db"), reverse=True)
    
    if not backups:
        print("No backups found.")
        return []
    
    print("\n📦 Available backups:")
    for backup in backups:
        size_mb = backup.stat().st_size / (1024 * 1024)
        print(f"  - {backup.name} ({size_mb:.2f} MB)")
    
    return backups

def restore_backup(backup_path: Path):
    """
    Restore a backup to the main database.
    
    Args:
        backup_path: Path to the backup file
    """
    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_path}")
        return False
    
    # Create a backup of current state before restoring
    create_backup(reason="pre_restore")
    
    shutil.copy2(backup_path, DB_PATH)
    print(f"✅ Database restored from: {backup_path}")
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_backups()
    elif len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            print("Usage: python backup_db.py restore <backup_filename>")
            list_backups()
        else:
            backup_file = BACKUP_DIR / sys.argv[2]
            restore_backup(backup_file)
    else:
        create_backup(reason="manual")
