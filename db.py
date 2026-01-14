import os

# Database configuration


def get_db_secrets():
    return {
        'username': os.getenv('DB_USERNAME'),
        'password': os.getenv('DB_PASSWORD'),
        'host': os.getenv('DB_HOST'),
        'port': os.getenv('DB_PORT'),
        'database': os.getenv('DB_DATABASE'),
    }

db_secrets = get_db_secrets()

# Define the URL to connect to the database
url = f"postgresql://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets.get('port', 5432)}/{db_secrets['database']}?sslmode=require"

# Other code...