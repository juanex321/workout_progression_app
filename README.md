# Workout Progression App

A Streamlit-based workout tracking application that helps users track their workout progress, manage exercises, and follow progressive overload principles.

## Features

- **Workout Planning**: Structured workout programs with customizable exercises
- **Progressive Overload**: Smart weight and rep recommendations based on past performance
- **Session Tracking**: Log sets, reps, weight, and RIR (Reps in Reserve)
- **Feedback System**: Track muscle soreness, pump, and workload
- **Data Persistence**: All your workout history is saved and never lost

## Tech Stack

- **Frontend/UI**: Streamlit
- **Database**: 
  - **Streamlit Cloud**: PostgreSQL (required for data persistence)
  - **Local**: SQLite (automatic, file-based)
- **Data Processing**: Pandas
- **ORM**: SQLAlchemy
- **Python Version**: 3.12+

## Quick Start

### Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

The app will automatically use SQLite for local development (no setup required).

## Deployment

### Streamlit Cloud

This app uses PostgreSQL for data persistence on Streamlit Cloud.

**Quick Setup:**
1. Get a free PostgreSQL database from [Neon.tech](https://neon.tech)
2. Configure database credentials in Streamlit Cloud secrets
3. Deploy!

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## Database

The app automatically detects the environment and uses the appropriate database:

- **Streamlit Cloud**: PostgreSQL (required for data persistence)
- **Local**: SQLite (automatic, file-based)

### Why PostgreSQL for Cloud?

Streamlit Cloud has a read-only filesystem, which means SQLite databases cannot persist data between app restarts. PostgreSQL ensures that all your workout data is permanently saved in the cloud.

## Project Structure

- `app.py` - Main Streamlit application with UI and workout tracking functionality
- `db.py` - SQLAlchemy database models and connection management
- `services.py` - Business logic services for session and set management
- `progression.py` - Weight and rep recommendation algorithm
- `plan.py` - Workout planning logic
- `init_db.py` - Database initialization script
- `check_db.py` - Database health check utility
- `migrate_sqlite_to_postgres.py` - Migration script for moving data to PostgreSQL

## Utilities

### Check Database Health

```bash
python check_db.py
```

This will show:
- Database type (SQLite or PostgreSQL)
- Connection status
- Statistics (sessions, sets, feedback, exercises)
- Recent sessions

### Migrate Data

If you have existing workout data in SQLite and want to move to PostgreSQL:

```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
python migrate_sqlite_to_postgres.py
```

## Contributing

Contributions are welcome! Please ensure your changes follow the existing code style and patterns.

## License

MIT License
