import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


# Locate the project folder: one level above the scripts folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load connection settings from the project's private .env file.
load_dotenv(PROJECT_ROOT / ".env")


def main():
    # Connect from your laptop to PostgreSQL running in Docker.
    # Read the credentials from environment variables.
    with psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    ) as connection:

        # A cursor sends SQL queries and retrieves their results.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user;")

            # This query returns one row containing two values.
            database_name, username = cursor.fetchone()

            print("Connection successful!")
            print(f"Database: {database_name}")
            print(f"User: {username}")


# Run main() only when this file is executed directly.
if __name__ == "__main__":
    main()