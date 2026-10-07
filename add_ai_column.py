import sqlite3

DB_PATH = "instance/lost_found.db"

connection = sqlite3.connect(DB_PATH)

cursor = connection.cursor()

# Check existing columns
cursor.execute("PRAGMA table_info(item_report)")

columns = [row[1] for row in cursor.fetchall()]

if "ai_analysis" not in columns:

    cursor.execute("""
        ALTER TABLE item_report
        ADD COLUMN ai_analysis TEXT
    """)

    print("ai_analysis column added successfully.")

else:

    print("ai_analysis column already exists.")

connection.commit()

connection.close()

print("Database update completed.")