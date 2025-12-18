# app/db/repositories/muscles.py

def list_muscles(conn):
    cur = conn.execute("SELECT id, name FROM muscle ORDER BY name")
    return cur.fetchall()
