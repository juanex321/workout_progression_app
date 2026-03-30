"""
Data recovery tool to inspect and recover workout data from database files.
"""
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from backup_db import BACKUP_DIR, DB_PATH
import sys

def inspect_database(db_path: Path):
    """
    Inspect a database file and show what data it contains.
    """
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        return None
    
    print(f"\n🔍 Inspecting: {db_path}")
    print(f"   Size: {db_path.stat().st_size / 1024:.2f} KB")
    
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    
    print("\n📊 Tables found:")
    for table_name in inspector.get_table_names():
        print(f"   - {table_name}")
    
    # Check sessions table
    if 'sessions' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('sessions')]
        print(f"\n📋 Sessions table columns: {', '.join(columns)}")
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM sessions"))
            count = result.scalar()
            print(f"   Total sessions: {count}")
            
            if count > 0:
                result = conn.execute(text("SELECT * FROM sessions ORDER BY date ASC LIMIT 10"))
                print("\n   Sample session records (first 10):")
                for row in result:
                    print(f"     {dict(row._mapping)}")
    
    # Check sets table
    if 'sets' in inspector.get_table_names():
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM sets"))
            count = result.scalar()
            print(f"\n   Total logged sets: {count}")
    
    # Check feedback table
    if 'feedback' in inspector.get_table_names():
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM feedback"))
            count = result.scalar()
            print(f"   Total feedback entries: {count}")
    
    engine.dispose()
    return True

def find_best_backup():
    """Find the backup with the most data."""
    if not BACKUP_DIR.exists():
        print("No backups directory found.")
        return None
    
    backups = list(BACKUP_DIR.glob("workout_backup_*.db"))
    if not backups:
        print("No backups found.")
        return None
    
    print("\n🔍 Analyzing backups for data recovery...\n")
    
    best_backup = None
    max_data = 0
    
    for backup in backups:
        engine = create_engine(f"sqlite:///{backup}")
        try:
            with engine.connect() as conn:
                sets_count = conn.execute(text("SELECT COUNT(*) FROM sets")).scalar()
                sessions_count = conn.execute(text("SELECT COUNT(*) FROM sessions")).scalar()
                feedback_count = conn.execute(text("SELECT COUNT(*) FROM feedback")).scalar()
                
                total_data = sets_count + feedback_count
                
                print(f"{backup.name}:")
                print(f"  Sessions: {sessions_count}, Sets: {sets_count}, Feedback: {feedback_count}")
                
                if total_data > max_data:
                    max_data = total_data
                    best_backup = backup
        except Exception as e:
            print(f"  ⚠️  Error reading: {e}")
        finally:
            engine.dispose()
    
    if best_backup:
        print(f"\n✅ Best backup found: {best_backup.name}")
        print(f"   Contains {max_data} data records")
    
    return best_backup

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "current":
            inspect_database(DB_PATH)
        elif sys.argv[1] == "find":
            find_best_backup()
        else:
            # Inspect specific backup
            backup_file = BACKUP_DIR / sys.argv[1]
            inspect_database(backup_file)
    else:
        print("Usage:")
        print("  python recover_data.py current          - Inspect current database")
        print("  python recover_data.py find             - Find best backup")
        print("  python recover_data.py <backup_file>    - Inspect specific backup")
