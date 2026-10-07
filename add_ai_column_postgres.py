import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable is not set.")

# Render may provide postgres://
# SQLAlchemy/psycopg expects postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )

engine = create_engine(DATABASE_URL)

with engine.connect() as connection:

    # Check whether the column already exists
    result = connection.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'item_report'
        AND column_name = 'ai_analysis'
    """))

    column_exists = result.fetchone()

    if column_exists:

        print("ai_analysis column already exists.")

    else:

        connection.execute(text("""
            ALTER TABLE item_report
            ADD COLUMN ai_analysis TEXT
        """))

        connection.commit()

        print("ai_analysis column added successfully.")

print("Database migration completed.")
