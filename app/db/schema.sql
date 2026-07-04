CREATE TABLE IF NOT EXISTS app_user (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    last_login DATE,
    weight_unit TEXT DEFAULT 'lb',
    week_start TEXT DEFAULT 'sun',
    body_model TEXT DEFAULT 'male',
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
    avg_reps DOUBLE PRECISION,
    max_reps INTEGER,
    workout_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (workout_id) REFERENCES workout (id),
    FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id)
);

-- Per-set weight/reps. exercise.weight_used/num_of_sets/avg_reps/max_reps
-- stay as derived rollups (top-set weight, count, avg/max reps) computed
-- from these rows -- kept for quick-list display, no longer the source of
-- truth for stats/volume.
CREATE TABLE IF NOT EXISTS exercise_set (
    id SERIAL PRIMARY KEY,
    exercise_id INTEGER NOT NULL,
    set_index INTEGER NOT NULL,
    weight_used DOUBLE PRECISION,
    weight_unit TEXT,
    weight_used_kg DOUBLE PRECISION,
    reps INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exercise_id) REFERENCES exercise (id) ON DELETE CASCADE,
    UNIQUE (exercise_id, set_index)
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

-- Fixed, non-user-editable anatomical regions for the muscle-map picker.
-- Seeded from utils/body_regions.py (scripts/migrate_body_regions.py).
CREATE TABLE IF NOT EXISTS body_region (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    view TEXT NOT NULL
);

-- Which tapped regions surface a given exercise_catalog entry. One
-- exercise can have several regions (bench = chest + triceps + delts).
CREATE TABLE IF NOT EXISTS exercise_catalog_region (
    exercise_catalog_id INTEGER NOT NULL,
    region_slug TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'primary',
    PRIMARY KEY (exercise_catalog_id, region_slug),
    FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id) ON DELETE CASCADE,
    FOREIGN KEY (region_slug) REFERENCES body_region (slug)
);

-- Exercises you haven't logged yet, sourced from wger (CC-BY-SA), shown
-- de-emphasized below your own exercises in the region shortlist.
CREATE TABLE IF NOT EXISTS suggested_exercise (
    id SERIAL PRIMARY KEY,
    wger_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    image_path TEXT,
    license_author TEXT,
    license_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suggested_exercise_region (
    suggested_exercise_id INTEGER NOT NULL,
    region_slug TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'primary',
    PRIMARY KEY (suggested_exercise_id, region_slug),
    FOREIGN KEY (suggested_exercise_id) REFERENCES suggested_exercise (id) ON DELETE CASCADE,
    FOREIGN KEY (region_slug) REFERENCES body_region (slug)
);

-- Best-effort link from a catalog entry to a matching wger suggestion,
-- used only to borrow its preview image. Computed with rapidfuzz when
-- the catalog entry is created (see exercise_catalog_repo.get_or_create).
ALTER TABLE exercise_catalog ADD COLUMN IF NOT EXISTS suggested_exercise_id INTEGER REFERENCES suggested_exercise (id);
