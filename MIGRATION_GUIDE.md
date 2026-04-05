# Database Migration Guide

## Important: Never Lose Your Data Again

This app now uses Alembic for safe database migrations. Your workout data is automatically backed up before any changes.

## Quick Start

### First Time Setup (Existing Users)

If you have existing workout data:

1. Create a backup:
   ```bash
   python backup_db.py
   ```

2. Run the Alembic migration to add new columns if needed:
   ```bash
   alembic upgrade head
   ```

3. Migrate your session data:
   ```bash
   python migrate_sessions.py
   ```

4. Verify everything worked:
   ```bash
   python recover_data.py current
   ```

### New Users

Just run:
```bash
python init_db.py
uvicorn api.index:app --reload --port 8000
cd frontend && npm run dev
```

## Data Recovery

### List Available Backups

```bash
python backup_db.py list
```

### Inspect Current Database

```bash
python recover_data.py current
```

### Find Best Backup (most data)

```bash
python recover_data.py find
```

### Restore from Backup

```bash
python backup_db.py restore workout_backup_20260114_120000_pre_migration.db
```

## How It Works

1. Automatic backups are created before schema changes
2. Alembic adds or modifies columns without data loss
3. Rollback support is available for schema changes
4. Recovery tools can inspect and restore from backups

## Future Schema Changes

When the schema changes in a future update:

1. Pull the latest code
2. Run `alembic upgrade head`
3. Your data will be preserved automatically
