from app.db.connection import get_conn

def migrate_exercise_weight_to_real():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=OFF;")
    cur.execute("BEGIN;")

    # 1. Rename old table
    cur.execute("ALTER TABLE exercise RENAME TO exercise_old;")

    # 2. Create new table with REAL weight_used
    cur.execute("""
        CREATE TABLE exercise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weight_used REAL,
            num_of_sets INTEGER,
            workout_id INTEGER,
            FOREIGN KEY (workout_id) REFERENCES workout (id)
        );
    """)

    # 3. Copy existing data
    cur.execute("""
        INSERT INTO exercise (id, weight_used, num_of_sets, workout_id)
        SELECT id, weight_used, num_of_sets, workout_id FROM exercise_old;
    """)

    # 4. Drop old table
    cur.execute("DROP TABLE exercise_old;")

    cur.execute("COMMIT;")
    cur.execute("PRAGMA foreign_keys=ON;")
    conn.close()
    print("✅ exercise.weight_used changed to REAL successfully")

if __name__ == "__main__":
    migrate_exercise_weight_to_real()
