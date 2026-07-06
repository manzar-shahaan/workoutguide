# utils/tags.py
#
# Curated exercise-tag vocabulary. Tags are the descriptive "what is this"
# axis (many per exercise) -- an activity like badminton is [cardio],
# [agility], [plyometrics] at once. They're deliberately separate from:
#   - metric_type   (how you log it: resistance = weight/reps, endurance =
#                    time/distance) -- one per exercise, drives the form
#   - body regions  (which muscles) -- the muscle-map axis
# so analytics like "45 minutes of cardio this week" can sum durations
# across every exercise tagged `cardio` regardless of how it was logged.
#
# Fixed/curated (not user-editable) so the tag set stays clean for
# aggregation; seeded into the `tag` table by scripts/migrate_tags.py.
# `sort_order` controls chip order on the add/edit form.

TAGS = [
    # (slug, display name, sort_order)
    ("strength", "Strength", 10),
    ("cardio", "Cardio", 20),
    ("mobility", "Mobility", 30),
    ("plyometrics", "Plyometrics", 40),
    ("agility", "Agility", 50),
    ("balance", "Balance", 60),
    ("core", "Core", 70),
    ("power", "Power", 80),
    ("endurance", "Endurance", 90),
    # Cardio sub-types (formerly cardio_target) -- now just tags, so
    # "minutes of HIIT" aggregates the same way any other tag does.
    ("steady", "Steady state", 100),
    ("hiit", "HIIT", 110),
    ("intervals", "Intervals", 120),
    ("sprints", "Sprints", 130),
]

TAG_SLUGS = {slug for slug, *_ in TAGS}
