# Pace

Workout logging web app built with Flask + Postgres. Users track workouts, exercises, and weight progression.

## Features

- Installable PWA: manifest + service worker, launches straight to the home/log screen, persistent login (Flask-Login remember-me).
- Home screen has a tappable front/back muscle-map picker (`body-highlighter`) — tap regions to narrow a shortlist of your own exercises (prioritized) plus unlogged suggestions sourced from wger (de-emphasized), each with a preview image. Regions you haven't trained in a while pulse (white → grey → black → hold, repeating) so the map doubles as a "what needs work" prompt. A Strength/Cardio switch in the map's header (`home.js`) jumps straight to the add-exercise form pre-set to "Time & distance" + the Cardio tag, since a timed activity has no regions to tap.
- Exercises are classified along three independent axes, not one rigid category:
  - **metric_type** (`metric-type-picker.js`) — *how you log it*: "Weights & reps" (resistance: weight × reps per set) or "Time & distance" (endurance: duration + optional distance per interval, one row per interval so HIIT/intervals get several). One per exercise; drives which fields the form shows.
  - **tags** (`tag-picker.js`) — *what it is*, a curated multi-select (Cardio, Strength, Mobility, Plyometrics, Agility, Balance, Core, Power, Endurance, Steady state, HIIT, Intervals, Sprints — `utils/tags.py`). Many per exercise, e.g. badminton = `[Cardio, Agility, Plyometrics]`, so "minutes of cardio this week" can sum durations across every tagged exercise regardless of what it's called. Optional — untagged exercises log fine, they just won't surface in tag-based rollups.
  - **body regions** (`region-picker.js`) — *which muscles*, unchanged: tap in priority order, unlimited regions. Resistance exercises only; endurance clears any region tags since a run shouldn't count toward muscle freshness.
- Workouts per day with multiple exercises, each logged as real per-set/per-interval rows (weight × reps, or duration + distance — not an averaged summary).
- Exercise catalog per user — rename/merge templates from the "Manage exercises" account page, which shows each template's metric type, tags, and regions.
- Weight tracking with lb/kg support and normalized kg values; distance tracking with mi/km support.
- Stats dashboard with calendar view and region/exercise progression charts.

## Data model overview

- `app_user`: account data, weight unit preference, week start.
- `workout`: date, user_id, optional notes.
- `exercise_catalog`: user-specific exercise names/templates, with `metric_type` (resistance/endurance) driving which fields a logged entry populates.
- `tag`: fixed, non-user-editable descriptive vocabulary (seeded from `utils/tags.py`).
- `exercise_catalog_tag`: which tags apply to a catalog entry (many-to-many, unordered) — the "what is this" classification, independent of metric_type and regions.
- `exercise`: logged entries with optional `exercise_name` and `exercise_catalog_id`; `weight_used`/`num_of_sets`/`avg_reps`/`max_reps`/`total_duration_seconds`/`total_distance`/`distance_unit` are derived rollups for quick-list display, not the source of truth.
- `exercise_set`: per-set weight/reps (resistance) or per-interval duration/distance (endurance) rows — the actual source of truth for volume, progression, and per-set/interval display. A given exercise only ever populates one pair, per its catalog `metric_type`.
- `body_region`: fixed, non-user-editable anatomical regions for the muscle-map (seeded from `utils/body_regions.py`, keyed to `body-highlighter`'s SVG).
- `exercise_catalog_region`: which regions a given catalog exercise hits, with a `rank` (1 = primary, 2 = secondary, ...) set by tap order in the picker. Resistance exercises only — endurance entries carry no region tags.
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
- `scripts/migrate_modality.py`: adds `exercise_catalog.modality`/`cardio_target`, backfills modality from the old muscle category, makes `muscle_id` nullable, and tightens the catalog's unique constraint to `(user_id, name)`. Refuses to tighten the constraint if it finds the same exercise name under two different muscles — resolve those first. Superseded by `migrate_tags.py` + `migrate_drop_modality.py`; kept as a historical record for existing DBs that predate the tag split. Re-runnable.
- `scripts/migrate_drop_muscle.py`: drops `exercise_catalog.muscle_id`, `exercise_muscle`, and `muscle` entirely. Run any time after `migrate_modality.py` has been applied and the app has been running on the region/modality model — nothing reads these anymore. Re-runnable.
- `scripts/migrate_cardio_sets.py`: adds `exercise_set.duration_seconds`/`distance`/`distance_unit` (per interval) and `exercise.total_duration_seconds`/`total_distance`/`distance_unit` (rollups), and drops the stale `NOT NULL` on `exercise.weight_unit` (endurance rows have no weight unit). Re-runnable.
- `scripts/migrate_tags.py`: Phase 1 of the modality → metric_type + tags split. Adds the `tag`/`exercise_catalog_tag` tables (seeded from `utils/tags.py`) and `exercise_catalog.metric_type`, then backfills `metric_type` + tags from the old `modality`/`cardio_target` columns (cardio → endurance + `[cardio]` tag, cardio_target folded in as its own tag, e.g. `[cardio, hiit]`). Safe to run before any UI change. Re-runnable — the backfill step is skipped once `migrate_drop_modality.py` has run.
- `scripts/migrate_drop_modality.py`: Phase 3 — drops `exercise_catalog.modality`/`cardio_target` entirely. Run only after `migrate_tags.py` has been applied and the app has been running on metric_type + tags. Re-runnable.
- `scripts/report_tagging_status.py`: read-only report of `exercise_catalog` classification — resistance exercises missing body-region tags (actionable, since those won't show up in the muscle-map shortlist), plus an informational count of exercises with no descriptive tags (tags are optional, so this isn't a problem to fix, just visibility).
- `scripts/seed_sample_data.py`: optional seed data (tags regions on resistance exercises, `[cardio]` + duration/distance on endurance ones).
- `scripts/smoke_db.py`: quick DB connectivity check.

## Legacy import

Importer supports multiple JSON shapes (array, object, or NDJSON) and normalizes into a canonical workout format. It can parse weight values with lb/kg suffixes and extract exercise names from notes. Legacy free-text muscle names can't be reliably mapped onto the fixed region taxonomy (e.g. "arms" alone doesn't say biceps vs. triceps vs. forearm), so imported exercises land untagged by region and get body-map tags later via the add/edit form — the one exception is a legacy "cardio" muscle bucket, which is recognized and classified as `metric_type=endurance` + a `[cardio]` tag automatically.

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
