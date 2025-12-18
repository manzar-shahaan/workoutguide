from pathlib import Path
from app.db.connection import get_conn

def init_db():
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    conn = get_conn()
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("✅ Database initialized with schema.sql")

if __name__ == "__main__":
    init_db()
