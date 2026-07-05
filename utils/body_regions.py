# utils/body_regions.py
#
# Fixed anatomical region list used by the muscle-map exercise picker.
# Slugs and front/back placement come from the `body-highlighter` SVG
# (MIT licensed, https://github.com/lahaxearnaud/body-highlighter) so the
# frontend's click events map onto these rows with no translation layer.
# Excludes body-highlighter's non-taggable decorative regions (head, neck,
# knees, left/right-soleus) since nobody logs an exercise against those.

REGIONS = [
    # (slug, display name, view)
    ("chest", "Chest", "anterior"),
    ("biceps", "Biceps", "anterior"),
    ("triceps", "Triceps", "anterior"),
    ("forearm", "Forearms", "anterior"),
    ("front-deltoids", "Front delts", "anterior"),
    ("abs", "Abs", "anterior"),
    ("obliques", "Obliques", "anterior"),
    ("quadriceps", "Quads", "anterior"),
    ("abductors", "Abductors", "anterior"),
    ("back-deltoids", "Rear delts", "posterior"),
    ("trapezius", "Traps", "posterior"),
    ("upper-back", "Upper back", "posterior"),
    ("lower-back", "Lower back", "posterior"),
    ("hamstring", "Hamstrings", "posterior"),
    ("gluteal", "Glutes", "posterior"),
    ("adductor", "Adductors", "posterior"),
    ("calves", "Calves", "posterior"),
]

REGION_SLUGS = {slug for slug, *_ in REGIONS}

# wger's 15 muscles don't cover every region we care about (no separate
# "hip adductor"/"hip abductor"/"posterior deltoid"/"forearm flexor"/
# "erector spinae" entries), so those 5 regions get nothing from
# WGER_MUSCLE_TO_REGION alone. Supplemental: scan the exercise NAME
# (not description -- too many false positives) for these keywords.
REGION_NAME_KEYWORDS = {
    "forearm": ["forearm", "wrist curl", "reverse curl", "farmer"],
    "lower-back": ["hyperextension", "good morning", "back extension", "lower back", "superman"],
    "adductor": ["adductor", "groin"],
    "abductors": ["abductor", "hip abduction", "clamshell", "band walk", "lateral walk"],
    "back-deltoids": ["rear delt", "reverse fly", "reverse pec deck", "face pull", "rear lateral"],
}

# wger muscle id -> region slug. wger's muscle names are the same Latin
# anatomical terms body-highlighter already maps from in its own alias
# table, so this is a direct id lookup, not a fuzzy match.
WGER_MUSCLE_TO_REGION = {
    1: "biceps",        # Biceps brachii
    2: "front-deltoids",  # Anterior deltoid
    3: "abs",            # Serratus anterior
    4: "chest",          # Pectoralis major
    5: "triceps",        # Triceps brachii
    6: "abs",            # Rectus abdominis
    7: "calves",         # Gastrocnemius
    8: "gluteal",        # Gluteus maximus
    9: "trapezius",      # Trapezius
    10: "quadriceps",    # Quadriceps femoris
    11: "hamstring",     # Biceps femoris
    12: "upper-back",    # Latissimus dorsi
    13: "biceps",        # Brachialis
    14: "obliques",      # Obliquus externus abdominis
    15: "calves",        # Soleus
}
