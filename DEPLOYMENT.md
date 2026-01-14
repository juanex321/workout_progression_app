# Deployment Guide - Streamlit Cloud

## Setting Up PostgreSQL Database

### Step 1: Create Database on Streamlit Cloud

1. Go to your app settings on Streamlit Cloud
2. Navigate to **"Advanced settings"** → **"Secrets"**
3. Add the following configuration:

```toml
[connections.workout_db]
type = "sql"
dialect = "postgresql"
host = "YOUR_DB_HOST"
port = 5432
database = "YOUR_DB_NAME"
username = "YOUR_DB_USERNAME"
password = "YOUR_DB_PASSWORD"
```

### Step 2: Get a Free PostgreSQL Database

Streamlit Cloud doesn't provide databases directly, but you can use free options:

#### Option A: Neon (Recommended - Easiest)

1. Go to https://neon.tech
2. Sign up for free account
3. Create a new project
4. Copy the connection details:
   - Host: `ep-xxx-xxx.us-east-2.aws.neon.tech`
   - Database: `neondb`
   - Username: Your username
   - Password: Your password
5. Paste into Streamlit Cloud secrets (format above)

#### Option B: Supabase

1. Go to https://supabase.com
2. Create a new project
3. Go to Project Settings → Database
4. Copy connection details
5. Paste into Streamlit Cloud secrets

#### Option C: ElephantSQL

1. Go to https://www.elephantsql.com
2. Create a free "Tiny Turtle" instance
3. Copy connection URL
4. Parse URL into individual components for secrets

### Step 3: Deploy

1. Push your code to GitHub
2. Deploy on Streamlit Cloud
3. Configure secrets as shown above
4. App will automatically:
   - Detect PostgreSQL configuration
   - Create database tables
   - Persist all workout data permanently! ✅

## Local Development

For local development, you can either:

### Option 1: Use SQLite (Simpler)
Just run the app - it will automatically use SQLite:
```bash
streamlit run app.py
```

### Option 2: Use PostgreSQL Locally
1. Install PostgreSQL locally
2. Create `.streamlit/secrets.toml` with your local database credentials (see `.streamlit/secrets.toml.example`)
3. Run the app

## Verifying Database Connection

When the app starts, check the terminal output:
- `💾 Using SQLite database: workout.db` = Local SQLite mode
- `🌐 Using PostgreSQL database (Streamlit Cloud)` = Cloud PostgreSQL mode

## Troubleshooting

### "Could not connect to database"
- Check that secrets are configured correctly in Streamlit Cloud settings
- Verify database host/port/credentials are correct
- Make sure database allows connections from external IPs

### "relation does not exist"
- Tables haven't been created yet
- Check app logs for `init_db()` errors
- Database user may not have CREATE TABLE permissions

### Data not persisting
- If using SQLite on Streamlit Cloud = Won't work (read-only filesystem)
- If using PostgreSQL = Check database credentials
- Check app logs for write errors

## Migration from SQLite to PostgreSQL

If you have existing workout data in SQLite that you want to migrate to PostgreSQL:

1. Set the `DATABASE_URL` environment variable with your PostgreSQL connection string
2. Run the migration script:
   ```bash
   python migrate_sqlite_to_postgres.py
   ```

This will copy all your workout history, sessions, sets, and feedback to the PostgreSQL database.
