import os
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://workoutguide:workoutguide@localhost:5432/workoutguide",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)


def get_conn():
    return engine.connect()
