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

-- metric_type is how the exercise is logged (and thus how the form/
-- display behave): 'resistance' = weight x reps per set, 'endurance' =
-- duration (+ optional distance) per interval. What the exercise *is*
-- (cardio/strength/agility/...) lives in exercise_catalog_tag; which
-- muscles it hits lives in exercise_catalog_region. All three are
-- independent axes.
CREATE TABLE IF NOT EXISTS exercise_catalog (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    metric_type TEXT NOT NULL DEFAULT 'resistance',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id),
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS exercise (
    id SERIAL PRIMARY KEY,
    exercise_catalog_id INTEGER,
    exercise_name TEXT,
    weight_used DOUBLE PRECISION,
    weight_unit TEXT DEFAULT 'lb',
    weight_used_kg DOUBLE PRECISION,
    num_of_sets INTEGER,
    avg_reps DOUBLE PRECISION,
    max_reps INTEGER,
    total_duration_seconds INTEGER,
    total_distance DOUBLE PRECISION,
    distance_unit TEXT,
    workout_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (workout_id) REFERENCES workout (id),
    FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id)
);

-- Per-set weight/reps (resistance metric_type) or per-interval
-- duration/distance (endurance metric_type) -- a given exercise only ever
-- populates one pair, depending on its catalog metric_type.
-- exercise.weight_used/num_of_sets/avg_reps/max_reps/
-- total_duration_seconds/total_distance stay as derived rollups computed
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
    duration_seconds INTEGER,
    distance DOUBLE PRECISION,
    distance_unit TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exercise_id) REFERENCES exercise (id) ON DELETE CASCADE,
    UNIQUE (exercise_id, set_index)
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

-- Which tapped regions surface a given exercise_catalog entry, and in
-- what priority order (rank 1 = primary target, rank 2 = secondary, and
-- so on -- an exercise can hit as many regions as it actually trains,
-- e.g. bench = chest(1) + triceps(2) + front-deltoids(3)).
CREATE TABLE IF NOT EXISTS exercise_catalog_region (
    exercise_catalog_id INTEGER NOT NULL,
    region_slug TEXT NOT NULL,
    rank INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (exercise_catalog_id, region_slug),
    FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id) ON DELETE CASCADE,
    FOREIGN KEY (region_slug) REFERENCES body_region (slug)
);

-- Curated, non-user-editable descriptive tag vocabulary (Cardio,
-- Strength, Agility, HIIT, ...). Seeded from utils/tags.py
-- (scripts/migrate_tags.py). sort_order controls chip order on the form.
CREATE TABLE IF NOT EXISTS tag (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- Which descriptive tags apply to an exercise (many-to-many). Unlike
-- regions there's no rank -- all tags on an exercise are equal. This is
-- what powers cross-cutting analytics like "minutes tagged cardio".
CREATE TABLE IF NOT EXISTS exercise_catalog_tag (
    exercise_catalog_id INTEGER NOT NULL,
    tag_slug TEXT NOT NULL,
    PRIMARY KEY (exercise_catalog_id, tag_slug),
    FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_slug) REFERENCES tag (slug)
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
