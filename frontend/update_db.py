import sqlite3

conn = sqlite3.connect('fastclaw.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE keywords ADD COLUMN source VARCHAR DEFAULT 'manual'")
    cursor.execute("ALTER TABLE keywords ADD COLUMN parent_id INTEGER")
    cursor.execute("ALTER TABLE stores ADD COLUMN is_parsed_for_keywords BOOLEAN DEFAULT 0")
    conn.commit()
    print("Database schema updated successfully.")
except Exception as e:
    print(f"Error updating schema (might already exist): {e}")

conn.close()
