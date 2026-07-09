from pathlib import Path
import re
import sys

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn

def _iter_sql_statements(schema_text: str):
    # Strip `--` line comments before splitting on `;` -- otherwise a
    # semicolon inside a comment (e.g. "...tag; which muscles...") splits
    # a statement in the middle and produces a comment-only fragment that
    # psycopg2 rejects as an empty query.
    without_comments = "\n".join(
        re.sub(r"--.*", "", line) for line in schema_text.splitlines()
    )
    for statement in without_comments.split(";"):
        stmt = statement.strip()
        if stmt:
            yield stmt


def init_db():
    schema_path = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
    conn = get_conn()
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_text = f.read()
        for statement in _iter_sql_statements(schema_text):
            conn.exec_driver_sql(statement)
        conn.commit()
    finally:
        conn.close()
    print("✅ Database initialized with schema.sql")

if __name__ == "__main__":
    init_db()
