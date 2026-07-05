# app/db/repositories/exercise_catalog.py

from rapidfuzz import fuzz, process, utils
from sqlalchemy import bindparam, text

SUGGESTION_MATCH_THRESHOLD = 88


def list_for_regions(conn, user_id: int, region_slugs: list[str]):
    """
    Catalog entries matching ALL selected regions (bench = chest + triceps
    narrows correctly as more regions are tapped). Region tags are the only
    classification a strength/mobility/plyometrics entry has now, so an
    untagged entry simply doesn't show up here until it's tagged (via the
    picker on the add/edit form, or the backfill script) -- there's no
    muscle-category fallback anymore.
    """
    sql = text(
        """
        SELECT
            ec.id,
            ec.name,
            se.image_path,
            last.weight_used AS last_weight_used,
            last.weight_unit AS last_weight_unit,
            last.num_of_sets AS last_num_of_sets,
            last.workout_date AS last_workout_date,
            last_sets.sets AS last_sets_json
        FROM exercise_catalog ec
        LEFT JOIN suggested_exercise se ON se.id = ec.suggested_exercise_id
        LEFT JOIN LATERAL (
            SELECT e2.id, e2.weight_used, e2.weight_unit, e2.num_of_sets, w2.date AS workout_date
            FROM exercise e2
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE e2.exercise_catalog_id = ec.id
            ORDER BY w2.date DESC NULLS LAST, e2.created_at DESC
            LIMIT 1
        ) AS last ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                     jsonb_build_object('weight_used', s.weight_used, 'reps', s.reps)
                     ORDER BY s.set_index
                   ) AS sets
            FROM exercise_set s
            WHERE s.exercise_id = last.id
        ) AS last_sets ON TRUE
        WHERE ec.user_id = :user_id
          AND (
            SELECT COUNT(DISTINCT ecr.region_slug)
            FROM exercise_catalog_region ecr
            WHERE ecr.exercise_catalog_id = ec.id AND ecr.region_slug IN :slugs
          ) = :slug_count
        ORDER BY last.workout_date DESC NULLS LAST, ec.name
        """
    ).bindparams(bindparam("slugs", expanding=True))

    result = conn.execute(
        sql,
        {
            "user_id": user_id,
            "slugs": region_slugs,
            "slug_count": len(region_slugs),
        },
    )
    return result.mappings().all()


def _normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def list_for_region(conn, user_id: int, region_slug: str):
    """Catalog entries tagged with this region, for the stats exercise-picker."""
    sql = """
        SELECT DISTINCT ec.id, ec.name
        FROM exercise_catalog ec
        JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = ec.id
        WHERE ec.user_id = :user_id AND ecr.region_slug = :region_slug
        ORDER BY ec.name
    """
    result = conn.execute(text(sql), {"user_id": user_id, "region_slug": region_slug})
    return result.mappings().all()


def get_regions(conn, exercise_catalog_id: int) -> list[str]:
    """Region slugs tagged on this catalog entry, in rank order (primary first)."""
    result = conn.execute(
        text(
            """
            SELECT region_slug
            FROM exercise_catalog_region
            WHERE exercise_catalog_id = :id
            ORDER BY rank ASC
            """
        ),
        {"id": exercise_catalog_id},
    )
    return [row["region_slug"] for row in result.mappings().all()]


def list_all_with_counts_and_last(conn, user_id: int):
    sql = """
        SELECT
            ec.id,
            ec.name,
            COUNT(e.id) AS exercise_count,
            last.weight_used AS last_weight_used,
            last.weight_unit AS last_weight_unit,
            last.num_of_sets AS last_num_of_sets,
            last.workout_date AS last_workout_date,
            last_sets.sets AS last_sets_json
        FROM exercise_catalog ec
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        LEFT JOIN LATERAL (
            SELECT e2.id, e2.weight_used, e2.weight_unit, e2.num_of_sets, w2.date AS workout_date
            FROM exercise e2
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE e2.exercise_catalog_id = ec.id
            ORDER BY w2.date DESC NULLS LAST, e2.created_at DESC
            LIMIT 1
        ) AS last ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                     jsonb_build_object('weight_used', s.weight_used, 'reps', s.reps)
                     ORDER BY s.set_index
                   ) AS sets
            FROM exercise_set s
            WHERE s.exercise_id = last.id
        ) AS last_sets ON TRUE
        WHERE ec.user_id = :user_id
        GROUP BY ec.id, ec.name,
                 last.weight_used, last.weight_unit, last.num_of_sets, last.workout_date,
                 last_sets.sets
        ORDER BY last.workout_date DESC NULLS LAST, ec.name
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()

def list_all_with_details(conn, user_id: int):
    """
    Every catalog entry with modality/cardio_target/regions, for the Manage
    Exercises page. Regions come from a LATERAL subquery (pre-aggregated to
    one row per catalog entry) rather than a plain join, so joining in the
    exercise log count doesn't cross-multiply the two independent one-to-
    many relationships (each exercise log x each tagged region).
    """
    sql = """
        SELECT
            ec.id,
            ec.name,
            ec.modality,
            ec.cardio_target,
            COUNT(e.id) AS exercise_count,
            COALESCE(regions.names, '') AS regions
        FROM exercise_catalog ec
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        LEFT JOIN LATERAL (
            SELECT string_agg(br.name, ', ' ORDER BY ecr.rank) AS names
            FROM exercise_catalog_region ecr
            JOIN body_region br ON br.slug = ecr.region_slug
            WHERE ecr.exercise_catalog_id = ec.id
        ) AS regions ON TRUE
        WHERE ec.user_id = :user_id
        GROUP BY ec.id, ec.name, ec.modality, ec.cardio_target, regions.names
        ORDER BY ec.name
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()


def get_template(conn, user_id: int, template_id: int):
    sql = """
        SELECT id, name, modality, cardio_target
        FROM exercise_catalog
        WHERE user_id = :user_id AND id = :id
    """
    result = conn.execute(text(sql), {"user_id": user_id, "id": template_id})
    return result.mappings().fetchone()


def count_for_user(conn, user_id: int) -> int:
    sql = """
        SELECT COUNT(*) AS count
        FROM exercise_catalog
        WHERE user_id = :user_id
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    row = result.mappings().fetchone()
    return row["count"] if row else 0


def search_all_with_counts(conn, user_id: int, query: str):
    sql = """
        SELECT
            ec.id,
            ec.name,
            COUNT(e.id) AS exercise_count,
            last.weight_used AS last_weight_used,
            last.weight_unit AS last_weight_unit,
            last.num_of_sets AS last_num_of_sets,
            last.workout_date AS last_workout_date,
            last_sets.sets AS last_sets_json
        FROM exercise_catalog ec
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        LEFT JOIN LATERAL (
            SELECT e2.id, e2.weight_used, e2.weight_unit, e2.num_of_sets, w2.date AS workout_date
            FROM exercise e2
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE e2.exercise_catalog_id = ec.id
            ORDER BY w2.date DESC NULLS LAST, e2.created_at DESC
            LIMIT 1
        ) AS last ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                     jsonb_build_object('weight_used', s.weight_used, 'reps', s.reps)
                     ORDER BY s.set_index
                   ) AS sets
            FROM exercise_set s
            WHERE s.exercise_id = last.id
        ) AS last_sets ON TRUE
        WHERE ec.user_id = :user_id
          AND ec.name ILIKE :q
        GROUP BY ec.id, ec.name,
                 last.weight_used, last.weight_unit, last.num_of_sets, last.workout_date,
                 last_sets.sets
        ORDER BY ec.name
        LIMIT 25
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "q": f"%{query}%"},
    )
    return result.mappings().all()


def get_by_name(conn, user_id: int, name: str):
    name_norm = _normalize_name(name)
    if not name_norm:
        return None
    sql = """
        SELECT id, name
        FROM exercise_catalog
        WHERE user_id = :user_id AND name = :name
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "name": name_norm},
    )
    return result.mappings().fetchone()


def rename_template(
    conn,
    user_id: int,
    template_id: int,
    new_name: str,
) -> int | None:
    name_norm = _normalize_name(new_name)
    if not name_norm:
        raise ValueError("Template name is required.")

    current = get_template(conn, user_id, template_id)
    if current is None:
        return None

    if current["name"] == name_norm:
        return current["id"]

    existing = get_by_name(conn, user_id, name_norm)
    if existing:
        raise ValueError(
            "An exercise template with that name already exists. Use merge instead."
        )

    conn.execute(
        text(
            """
            UPDATE exercise_catalog
            SET name = :name
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": template_id, "user_id": user_id, "name": name_norm},
    )
    conn.execute(
        text(
            """
            UPDATE exercise
            SET exercise_name = :name
            WHERE exercise_catalog_id = :id
            """
        ),
        {"id": template_id, "name": name_norm},
    )
    conn.commit()
    return template_id


def merge_templates(
    conn,
    user_id: int,
    source_template_id: int,
    target_template_id: int,
    *,
    commit: bool = True,
) -> None:
    if source_template_id == target_template_id:
        raise ValueError("Pick two different templates to merge.")

    source = get_template(conn, user_id, source_template_id)
    target = get_template(conn, user_id, target_template_id)
    if source is None or target is None:
        raise ValueError("Template not found.")

    target_name = target["name"]

    conn.execute(
        text(
            """
            UPDATE exercise
            SET exercise_catalog_id = :target_id,
                exercise_name = :target_name
            WHERE exercise_catalog_id = :source_id
            """
        ),
        {
            "target_id": target_template_id,
            "target_name": target_name,
            "source_id": source_template_id,
        },
    )
    conn.execute(
        text(
            """
            UPDATE exercise
            SET exercise_name = :target_name
            WHERE exercise_catalog_id = :target_id
            """
        ),
        {"target_id": target_template_id, "target_name": target_name},
    )
    conn.execute(
        text(
            """
            DELETE FROM exercise_catalog
            WHERE id = :source_id AND user_id = :user_id
            """
        ),
        {"source_id": source_template_id, "user_id": user_id},
    )
    if commit:
        conn.commit()


def get_or_create(
    conn,
    user_id: int,
    name: str,
    *,
    modality: str = "strength",
    cardio_target: str | None = None,
    commit: bool = True,
) -> int | None:
    name_norm = _normalize_name(name)
    if not name_norm:
        return None
    existing = get_by_name(conn, user_id, name_norm)
    if existing:
        return existing["id"]
    result = conn.execute(
        text(
            """
            INSERT INTO exercise_catalog (user_id, name, modality, cardio_target)
            VALUES (:user_id, :name, :modality, :cardio_target)
            RETURNING id
            """
        ),
        {"user_id": user_id, "name": name_norm, "modality": modality, "cardio_target": cardio_target},
    )
    new_id = result.scalar_one()
    link_suggested_match(conn, new_id, name_norm, commit=False)
    if commit:
        conn.commit()
    return new_id


def set_modality(
    conn,
    exercise_catalog_id: int,
    modality: str,
    cardio_target: str | None = None,
    *,
    commit: bool = True,
) -> None:
    """
    Updates an existing catalog entry's modality/cardio_target -- used when
    an exercise is re-logged or edited with a different modality than it
    was originally created with.
    """
    conn.execute(
        text(
            """
            UPDATE exercise_catalog
            SET modality = :modality, cardio_target = :cardio_target
            WHERE id = :id
            """
        ),
        {"id": exercise_catalog_id, "modality": modality, "cardio_target": cardio_target},
    )
    if commit:
        conn.commit()


def link_suggested_match(conn, exercise_catalog_id: int, name: str, *, commit: bool = True) -> int | None:
    """
    Best-effort fuzzy match against the wger-sourced suggested_exercise
    table, used only to borrow a preview image for a catalog entry. Not
    exact-name lookup -- catalog names are free text ("db bench" should
    still find "Dumbbell Bench Press").
    """
    name_norm = _normalize_name(name)
    if not name_norm:
        return None

    rows = conn.execute(text("SELECT id, name FROM suggested_exercise")).mappings().all()
    if not rows:
        return None

    choices = {row["id"]: row["name"] for row in rows}
    match = process.extractOne(
        name_norm, choices, scorer=fuzz.WRatio, processor=utils.default_process
    )
    if match is None:
        return None

    _matched_name, score, matched_id = match
    if score < SUGGESTION_MATCH_THRESHOLD:
        return None

    conn.execute(
        text("UPDATE exercise_catalog SET suggested_exercise_id = :sid WHERE id = :id"),
        {"sid": matched_id, "id": exercise_catalog_id},
    )
    if commit:
        conn.commit()
    return matched_id


def tag_regions(conn, exercise_catalog_id: int, region_slugs: list[str], *, commit: bool = True) -> None:
    """
    Set this catalog entry's body-region tags to exactly the given list,
    in order -- region_slugs[0] becomes rank 1 (primary), region_slugs[1]
    rank 2, and so on, with no cap on how many regions one exercise can
    hit. This fully replaces the previous tag set rather than merging with
    it: the picker widget always prefills from whatever's currently
    tagged and resubmits the complete selection, so whatever's selected
    at save time -- including a region getting untapped -- is meant to be
    the authoritative set.
    """
    conn.execute(
        text("DELETE FROM exercise_catalog_region WHERE exercise_catalog_id = :id"),
        {"id": exercise_catalog_id},
    )
    for index, slug in enumerate(dict.fromkeys(region_slugs)):  # dedupe, keep order
        conn.execute(
            text(
                """
                INSERT INTO exercise_catalog_region (exercise_catalog_id, region_slug, rank)
                VALUES (:id, :slug, :rank)
                """
            ),
            {"id": exercise_catalog_id, "slug": slug, "rank": index + 1},
        )
    if commit:
        conn.commit()


def backfill_regions_from_suggestions(conn) -> int:
    """
    One-time (re-runnable) pass for exercise_catalog rows created before
    the muscle-map existed: fuzzy-match each untagged row's name against
    suggested_exercise and, on a confident match, copy that suggestion's
    region tags over. Rows with no good match stay untagged; the region
    shortlist query falls back to their broad muscle category for those.
    """
    untagged = conn.execute(
        text(
            """
            SELECT ec.id, ec.name
            FROM exercise_catalog ec
            LEFT JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = ec.id
            WHERE ecr.exercise_catalog_id IS NULL
            """
        )
    ).mappings().all()

    tagged_count = 0
    for row in untagged:
        matched_id = link_suggested_match(conn, row["id"], row["name"], commit=False)
        if matched_id is None:
            continue
        region_rows = conn.execute(
            text(
                """
                SELECT region_slug, role
                FROM suggested_exercise_region
                WHERE suggested_exercise_id = :sid
                ORDER BY (role = 'primary') DESC
                """
            ),
            {"sid": matched_id},
        ).mappings().all()
        slugs = [r["region_slug"] for r in region_rows]
        if slugs:
            tag_regions(conn, row["id"], slugs, commit=False)
            tagged_count += 1

    conn.commit()
    return tagged_count
