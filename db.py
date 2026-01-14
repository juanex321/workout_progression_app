port = db_secrets.get('port', 5432)
url = f"postgresql://{db_secrets.username}:{db_secrets.password}@{db_secrets.host}:{port}/{db_secrets.database}?sslmode=require"