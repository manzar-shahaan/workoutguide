# Workout Guide

Workout logging web app built with Flask + Postgres. Users track workouts, exercises, muscle groups, and weight progression.

## Features

- Installable PWA: manifest + service worker, launches straight to the home/log screen, persistent login (Flask-Login remember-me).
- Home screen has a tappable front/back muscle-map picker (`body-highlighter`) — tap 1-2 regions to narrow a shortlist of your own exercises (prioritized) plus unlogged suggestions sourced from wger (de-emphasized), each with a preview image.
- Manual "add/edit exercise" forms have a small inline version of the same map (`region-picker.js`) to tag up to 2 muscles when typing an exercise name directly, instead of only via the home-screen map.
- `body_model` account preference (male/female, default male) for the muscle map — stored and editable in Preferences now; `body-highlighter` only ships one unisex silhouette today so both currently render identically until a second asset is added.
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
- `body_region`: fixed, non-user-editable anatomical regions for the muscle-map (seeded from `utils/body_regions.py`, keyed to `body-highlighter`'s SVG).
- `exercise_catalog_region`: which regions surface a given catalog exercise (primary/secondary), e.g. bench press -> chest (primary), triceps + front-deltoids (secondary).
- `suggested_exercise` / `suggested_exercise_region`: unlogged exercises imported from wger.de (CC-BY-SA), shown below your own history in the region shortlist.

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
- `scripts/migrate_body_regions.py`: adds `body_region`/`exercise_catalog_region`/`suggested_exercise*` tables and seeds the 17 regions. Run this once on an existing DB.
- `scripts/import_wger_exercises.py`: pulls exercises from the public wger.de API into `suggested_exercise`, mirrors a small preview image for each locally. Re-runnable/idempotent (`--max N` to test with a small batch first).
- `scripts/backfill_exercise_regions.py`: fuzzy-matches existing `exercise_catalog` rows (logged before the muscle-map existed) against `suggested_exercise` to tag them with regions. Run after the two scripts above; re-runnable.
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
