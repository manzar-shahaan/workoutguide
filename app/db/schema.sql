CREATE TABLE IF NOT EXISTS app_user (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    last_login DATE,
    weight_unit TEXT DEFAULT 'lb',
    week_start TEXT DEFAULT 'sun',
    email TEXT UNIQUE NOT NULL,
    recovery_email TEXT,
    password_hash TEXT NOT NULL,
    totp_secret TEXT,
    totp_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS workout (
    id SERIAL PRIMARY KEY,
    date DATE,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES app_user (id)
);

CREATE TABLE IF NOT EXISTS muscle (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#64748b',
    is_default BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id),
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS exercise_catalog (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    muscle_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id),
    FOREIGN KEY (muscle_id) REFERENCES muscle (id),
    UNIQUE (user_id, muscle_id, name)
);

CREATE TABLE IF NOT EXISTS exercise (
    id SERIAL PRIMARY KEY,
    exercise_catalog_id INTEGER,
    exercise_name TEXT,
    weight_used DOUBLE PRECISION,
    weight_unit TEXT NOT NULL DEFAULT 'lb',
    weight_used_kg DOUBLE PRECISION,
    num_of_sets INTEGER,
    workout_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (workout_id) REFERENCES workout (id),
    FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id)
);

CREATE TABLE IF NOT EXISTS exercise_muscle (
    muscle_id INTEGER,
    exercise_id INTEGER,
    PRIMARY KEY (muscle_id, exercise_id),
    FOREIGN KEY (muscle_id) REFERENCES muscle (id),
    FOREIGN KEY (exercise_id) REFERENCES exercise (id)
);

CREATE TABLE IF NOT EXISTS totp_backup_code (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id)
);

CREATE TABLE IF NOT EXISTS access_code (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_by_user_id INTEGER,
    used_at TIMESTAMP,
    FOREIGN KEY (used_by_user_id) REFERENCES app_user (id),
    UNIQUE (name)
);
