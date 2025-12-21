import hashlib
import sys
from pathlib import Path

from sqlalchemy import text

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn

def smoke_test():
    conn = get_conn()
    try:
        # Create a simple password hash just for testing (never store plain text)
        password = "testpassword"
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Insert a test user with all required fields
        result = conn.execute(
            text(
                """
                INSERT INTO app_user (name, email, password_hash)
                VALUES (:name, :email, :password_hash)
                RETURNING id
                """
            ),
            {
                "name": "Manzar",
                "email": "manzar@example.com",
                "password_hash": password_hash,
            },
        )
        user_id = result.scalar_one()

        # Insert a workout for that user
        result = conn.execute(
            text(
                """
                INSERT INTO workout (date, user_id)
                VALUES (:date, :user_id)
                RETURNING id
                """
            ),
            {"date": "2025-11-12", "user_id": user_id},
        )
        workout_id = result.scalar_one()

        # Insert an exercise for that workout
        weight_used = 25
        weight_unit = "lb"
        weight_used_kg = weight_used * 0.45359237
        conn.execute(
            text(
                """
                INSERT INTO exercise (
                    weight_used, weight_unit, weight_used_kg, num_of_sets, workout_id
                )
                VALUES (:weight_used, :weight_unit, :weight_used_kg, :num_of_sets, :workout_id)
                """
            ),
            {
                "weight_used": weight_used,
                "weight_unit": weight_unit,
                "weight_used_kg": weight_used_kg,
                "num_of_sets": 3,
                "workout_id": workout_id,
            },
        )

        conn.commit()

        # Fetch all users and workouts to verify
        print("\nUsers:")
        for row in conn.execute(
            text("SELECT id, name, email, created_at FROM app_user")
        ).mappings():
            print(dict(row))

        print("\nWorkouts:")
        for row in conn.execute(
            text("SELECT id, date, user_id FROM workout")
        ).mappings():
            print(dict(row))
    finally:
        conn.close()

if __name__ == "__main__":
    smoke_test()
