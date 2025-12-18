CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    last_login DATE,
    weight_unit TEXT DEFAULT 'lb',
    email TEXT UNIQUE NOT NULL,
    recovery_email TEXT,
    password_hash TEXT NOT NULL,
    totp_secret TEXT,
    totp_enabled INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS workout (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE,
    user_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES user (id)
);

CREATE TABLE IF NOT EXISTS muscle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exercise (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weight_used REAL,
    num_of_sets INTEGER,
    workout_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (workout_id) REFERENCES workout (id)
);

CREATE TABLE IF NOT EXISTS exercise_muscle (
    muscle_id INTEGER,
    exercise_id INTEGER,
    PRIMARY KEY (muscle_id, exercise_id),
    FOREIGN KEY (muscle_id) REFERENCES muscle (id),
    FOREIGN KEY (exercise_id) REFERENCES exercise (id)
);

CREATE TABLE IF NOT EXISTS totp_backup_code (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    used INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id)
);
