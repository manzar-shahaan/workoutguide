# app/db/repositories/suggested_exercises.py
#
# wger-sourced exercises the user hasn't logged yet. Shown de-emphasized
# below the user's own history in the region-tap shortlist.

from sqlalchemy import bindparam, text


def list_for_regions(conn, user_id: int, region_slugs: list[str], *, limit: int = 20):
    sql = text(
        """
        SELECT se.id, se.name, se.image_path, se.license_author, se.license_name,
               primary_region.region_slug AS primary_region
        FROM suggested_exercise se
        JOIN LATERAL (
            SELECT region_slug
            FROM suggested_exercise_region
            WHERE suggested_exercise_id = se.id
            ORDER BY (region_slug IN :slugs) DESC, (role = 'primary') DESC
            LIMIT 1
        ) AS primary_region ON TRUE
        WHERE (
            SELECT COUNT(DISTINCT ser.region_slug)
            FROM suggested_exercise_region ser
            WHERE ser.suggested_exercise_id = se.id
              AND ser.region_slug IN :slugs
        ) = :slug_count
        AND se.id NOT IN (
            SELECT suggested_exercise_id
            FROM exercise_catalog
            WHERE user_id = :user_id AND suggested_exercise_id IS NOT NULL
        )
        ORDER BY se.name
        LIMIT :limit
        """
    ).bindparams(bindparam("slugs", expanding=True))

    result = conn.execute(
        sql,
        {"user_id": user_id, "slugs": region_slugs, "slug_count": len(region_slugs), "limit": limit},
    )
    return result.mappings().all()
