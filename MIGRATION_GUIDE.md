# Database Migration Guide

## ⚠️ IMPORTANT: Never Lose Your Data Again

This app now uses Alembic for safe database migrations. Your workout data is automatically backed up before any changes.

## Quick Start

### First Time Setup (Existing Users)

If you have existing workout data:

1. **Create a backup** (just to be safe):
   ```bash
   python backup_db.py
   ```

2. **Run the Alembic migration** to add new columns (if needed):
   ```bash
   alembic upgrade head
   ```

3. **Migrate your session data**:
   ```bash
   python migrate_sessions.py
   ```

4. **Verify everything worked**:
   ```bash
   python recover_data.py current
   ```

### New Users

Just run:
```bash
python init_db.py
streamlit run app.py
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

1. **Automatic Backups**: Created before any schema changes
2. **Safe Migrations**: Alembic adds/modifies columns without data loss
3. **Rollback Support**: Can revert to previous schema if needed
4. **Recovery Tools**: Inspect and restore from any backup

## Future Schema Changes

When the schema changes in a future update:

1. Pull the latest code
2. Run: `alembic upgrade head`
3. Your data will be preserved automatically!

## Manual Backup

You can create a manual backup at any time:

```bash
python backup_db.py
```

This creates a timestamped backup in the `db_backups/` directory.

## Troubleshooting

### "No sessions found to migrate"

This means your database schema doesn't have the required columns yet. Run:
```bash
alembic upgrade head
```

### "Schema compatibility issue"

The database schema is missing required columns. Run the Alembic migration:
```bash
alembic upgrade head
```

### "Database file not found"

You need to initialize the database first:
```bash
python init_db.py
```

## Migration Safety Features

- ✅ **Automatic backups** before any schema changes
- ✅ **Rollback support** if migration fails
- ✅ **Data verification** after migration
- ✅ **Recovery tools** to find and restore backups
- ✅ **No data loss** - all existing data is preserved
