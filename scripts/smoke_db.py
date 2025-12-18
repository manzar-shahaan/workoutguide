from app.db.connection import get_conn
import hashlib

def smoke_test():
    conn = get_conn()
    cursor = conn.cursor()

    # Create a simple password hash just for testing (never store plain text)
    password = "testpassword"
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    # Insert a test user with all required fields
    cursor.execute(
        "INSERT INTO user (name, email, password_hash) VALUES (?, ?, ?)",
        ("Manzar", "manzar@example.com", password_hash)
    )
    user_id = cursor.lastrowid

    # Insert a workout for that user
    cursor.execute(
        "INSERT INTO workout (date, user_id) VALUES (?, ?)",
        ("2025-11-12", user_id)
    )

    # Insert an exercise for that workout
    cursor.execute(
        "INSERT INTO exercise (weight_used, num_of_sets, workout_id) VALUES (?, ?, ?)",
        (25, 3, 1)
    )

    conn.commit()

    # Fetch all users and workouts to verify
    print("\nUsers:")
    for row in cursor.execute("SELECT id, name, email, created_at FROM user"):
        print(dict(row))

    print("\nWorkouts:")
    for row in cursor.execute("SELECT id, date, user_id FROM workout"):
        print(dict(row))

    conn.close()

if __name__ == "__main__":
    smoke_test()
