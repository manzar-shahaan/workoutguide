# app/db/repositories/freshness.py
#
# When each body region was last trained, for the "what needs work" pulse
# on the home-screen muscle map. Reuses the same
# exercise -> exercise_catalog -> exercise_catalog_region -> workout.date
# join the region-shortlist query already relies on.

from sqlalchemy import text


def last_trained_by_region(conn, user_id: int):
    """
    Returns {region_slug: {"primary": date|None, "secondary": date|None}}
    -- the most recent workout date this user hit that region as a primary
    or secondary target. Regions never trained (or never tagged) are
    omitted from the result; the caller fills those in.
    """
    sql = text(
        """
        SELECT ecr.region_slug, ecr.role, MAX(w.date) AS last_date
        FROM exercise_catalog_region ecr
        JOIN exercise_catalog ec ON ec.id = ecr.exercise_catalog_id
        JOIN exercise e ON e.exercise_catalog_id = ec.id
        JOIN workout w ON w.id = e.workout_id
        WHERE ec.user_id = :user_id
        GROUP BY ecr.region_slug, ecr.role
        """
    )
    rows = conn.execute(sql, {"user_id": user_id}).mappings().all()

    result: dict[str, dict[str, object]] = {}
    for row in rows:
        slug = row["region_slug"]
        result.setdefault(slug, {"primary": None, "secondary": None})
        result[slug][row["role"]] = row["last_date"]
    return result
