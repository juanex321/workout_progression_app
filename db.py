from urllib.parse import quote_plus

def get_database_url():
    """Get database URL based on environment."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'connections' in st.secrets and 'workout_db' in st.secrets['connections']:
            db_secrets = st.secrets['connections']['workout_db']
            # URL-encode username and password to handle special characters
            username = quote_plus(db_secrets['username'])
            password = quote_plus(db_secrets['password'])
            host = db_secrets['host']
            port = db_secrets.get('port', 5432)
            database = db_secrets['database']
            url = f"postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=require"
            print("🌐 Using PostgreSQL database (Streamlit Cloud)")
            return url
    except Exception as e:
        print(f"ℹ️  Not using Streamlit secrets: {e}")
    
    if 'DATABASE_URL' in os.environ:
        url = os.environ['DATABASE_URL']
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        print(f"🌐 Using PostgreSQL from DATABASE_URL")
        return url
    
    DB_PATH = Path("workout.db")
    print(f"💾 Using SQLite database: {DB_PATH}")
    return f"sqlite:///{DB_PATH}"
