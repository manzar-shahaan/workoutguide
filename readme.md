# Workout Guide

Workout logging web app built with Flask + Postgres. Users track workouts, exercises, muscle groups, and weight progression.

## Features

- Workouts per day with multiple exercises.
- Muscle groups with colors and active/inactive status.
- Exercise catalog per user and muscle, used for suggestions and stats.
- Weight tracking with lb/kg support and normalized kg values.
- Stats dashboard with calendar view and muscle/exercise progression charts.

## Data model overview

- `app_user`: account data, weight unit preference, week start.
- `workout`: date, user_id, optional notes.
- `muscle`: user-specific muscles with color and active flag.
- `exercise_catalog`: user-specific exercise names scoped to a muscle.
- `exercise`: logged entries with optional `exercise_name` and `exercise_catalog_id`.
- `exercise_muscle`: join table linking exercises to muscles.

## Setup

1) Install dependencies:
```
pip install -r requirements.txt
```

2) Configure the database:
- Default `DATABASE_URL` is in `app/db/connection.py`.
- Use a Postgres URL like:
```
postgresql+psycopg2://user:password@localhost:5432/workoutguide
```

3) Initialize schema:
```
python scripts/init_db.py
```

4) Run the app:
```
python run.py
```

## Migrations and scripts

- `scripts/migrate_exercise_real.py`: adds weight unit columns and backfills kg.
- `scripts/migrate_exercise_catalog.py`: adds exercise catalog table and links on exercise.
- `scripts/seed_sample_data.py`: optional seed data.
- `scripts/smoke_db.py`: quick DB connectivity check.

## Legacy import

Importer supports multiple JSON shapes (array, object, or NDJSON) and normalizes into a canonical workout format. It can parse weight values with lb/kg suffixes, map muscles, and extract exercise names from notes.

Example:
```
python scripts/import_legacy.py --path legacy.json --user-id 1 --dry-run --report import_report.json
```

Options:
- `--unit`: default unit when missing (`lb` or `kg`).
- `--tz`: timezone for datetime normalization.
- `--strict`: fail on invalid values instead of skipping.
- `--dedupe`: skip duplicate exercises on re-import.
- `--source`: force `legacy`, `generic`, or `auto`.

## Exercise suggestions

Exercise entry uses a free-text field. As you type, suggestions are pulled from the exercise catalog for the selected muscle and the total count of stored exercises is shown. If the name does not exist, it is created on save.

## Notes

Exercise `notes` remain intact and are not used as the primary exercise name. The `exercise_name` field is intended for clean cataloging and stats, while notes capture workout-specific details.
