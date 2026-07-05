# Pace

Workout logging web app built with Flask + Postgres. Users track workouts, exercises, and weight progression.

## Features

- Installable PWA: manifest + service worker, launches straight to the home/log screen, persistent login (Flask-Login remember-me).
- Home screen has a tappable front/back muscle-map picker (`body-highlighter`) — tap regions to narrow a shortlist of your own exercises (prioritized) plus unlogged suggestions sourced from wger (de-emphasized), each with a preview image. Regions you haven't trained in a while pulse (white → grey → black → hold, repeating) so the map doubles as a "what needs work" prompt.
- Manual "add/edit exercise" forms have an exercise-type toggle (Strength / Cardio / Mobility / Plyometrics) plus a small inline version of the same map (`region-picker.js`, `modality-picker.js`) — strength/mobility/plyometrics exercises are tagged with as many body regions as they actually hit, in the order tapped (1st = primary target, 2nd = secondary, and so on, with diminishing influence on freshness the further down the list); cardio exercises pick a type (Steady State / HIIT / Intervals / Sprints) instead, since "which muscle" isn't the useful classification for a run.
- `body_model` account preference (male/female, default male) for the muscle map — stored and editable in Preferences now; `body-highlighter` only ships one unisex silhouette today so both currently render identically until a second asset is added.
- Workouts per day with multiple exercises, each logged as real per-set rows (weight × reps per set, not an averaged summary).
- Exercise catalog per user, classified by modality + body regions (or cardio type) rather than a single muscle group — rename/merge templates from the "Manage exercises" account page.
- Weight tracking with lb/kg support and normalized kg values.
- Stats dashboard with calendar view and region/exercise progression charts.

## Data model overview

- `app_user`: account data, weight unit preference, week start.
- `workout`: date, user_id, optional notes.
- `exercise_catalog`: user-specific exercise names/templates, with `modality` (strength/cardio/mobility/plyometrics) and `cardio_target` (steady/hiit/intervals/sprints, cardio only).
- `exercise`: logged entries with optional `exercise_name` and `exercise_catalog_id`; `weight_used`/`num_of_sets`/`avg_reps`/`max_reps` are derived rollups for quick-list display, not the source of truth.
- `exercise_set`: per-set weight/reps rows — the actual source of truth for volume, progression, and per-set display.
- `body_region`: fixed, non-user-editable anatomical regions for the muscle-map (seeded from `utils/body_regions.py`, keyed to `body-highlighter`'s SVG).
- `exercise_catalog_region`: which regions a given catalog exercise hits, with a `rank` (1 = primary, 2 = secondary, ...) set by tap order in the picker. Strength/mobility/plyometrics only — cardio entries carry no region tags.
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
- `scripts/migrate_exercise_catalog.py`: adds exercise catalog table and links on exercise. Superseded by `schema.sql` for fresh installs; kept as a historical record for existing DBs that predate it.
- `scripts/migrate_body_regions.py`: adds `body_region`/`exercise_catalog_region`/`suggested_exercise*` tables and seeds the 17 regions. Run this once on an existing DB.
- `scripts/import_wger_exercises.py`: pulls exercises from the public wger.de API into `suggested_exercise`, mirrors a small preview image for each locally. Re-runnable/idempotent (`--max N` to test with a small batch first).
- `scripts/backfill_exercise_regions.py`: fuzzy-matches existing `exercise_catalog` rows (logged before the muscle-map existed) against `suggested_exercise` to tag them with regions. Run after the two scripts above; re-runnable.
- `scripts/migrate_exercise_sets.py`: adds `exercise_set` and backfills per-set rows from each exercise's rollup columns (num_of_sets rows at avg_reps, peak set bumped to max_reps). Re-runnable, no-op for exercises that already have set rows.
- `scripts/migrate_region_rank.py`: converts `exercise_catalog_region.role` (text, capped at primary/secondary) to `rank` (integer, unlimited regions per exercise). Re-runnable.
- `scripts/migrate_modality.py`: adds `exercise_catalog.modality`/`cardio_target`, backfills modality from the old muscle category, makes `muscle_id` nullable, and tightens the catalog's unique constraint to `(user_id, name)`. Refuses to tighten the constraint if it finds the same exercise name under two different muscles — resolve those first. Re-runnable.
- `scripts/migrate_drop_muscle.py`: drops `exercise_catalog.muscle_id`, `exercise_muscle`, and `muscle` entirely. Run any time after `migrate_modality.py` has been applied and the app has been running on the region/modality model — nothing reads these anymore. Re-runnable.
- `scripts/report_tagging_status.py`: read-only report of how many `exercise_catalog` entries are tagged vs. untagged (cardio = has `cardio_target`, everything else = has at least one region), plus a list of untagged entries by name. Useful before/after a manual tagging pass.
- `scripts/seed_sample_data.py`: optional seed data (also tags regions/modality on the seeded exercises).
- `scripts/smoke_db.py`: quick DB connectivity check.

## Legacy import

Importer supports multiple JSON shapes (array, object, or NDJSON) and normalizes into a canonical workout format. It can parse weight values with lb/kg suffixes and extract exercise names from notes. Legacy free-text muscle names can't be reliably mapped onto the fixed region taxonomy (e.g. "arms" alone doesn't say biceps vs. triceps vs. forearm), so imported exercises land untagged by region and get body-map tags later via the add/edit form — the one exception is a legacy "cardio" muscle bucket, which is recognized and classified as `modality=cardio` automatically.

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

Exercise entry uses a free-text field. As you type, suggestions are pulled from your full exercise catalog (name, last-logged date, last sets) and the total count of stored exercises is shown. If the name does not exist, it is created on save.

## Notes

Exercise `notes` remain intact and are not used as the primary exercise name. The `exercise_name` field is intended for clean cataloging and stats, while notes capture workout-specific details.
