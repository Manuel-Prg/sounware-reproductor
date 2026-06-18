from typing import Optional
from soundwave.library.database import Database, Song


RULE_FIELDS = {
    "genre": {"label": "Género", "op": "="},
    "artist": {"label": "Artista", "op": "="},
    "album": {"label": "Álbum", "op": "="},
    "year_min": {"label": "Año mínimo", "op": ">="},
    "year_max": {"label": "Año máximo", "op": "<="},
    "rating_min": {"label": "Valoración mínima", "op": ">="},
    "play_count_min": {"label": "Reproducciones mínimas", "op": ">="},
}


def build_query(rules: dict) -> tuple[str, list]:
    conditions = []
    params = []
    for key, value in rules.items():
        if not value and value != 0:
            continue
        if key == "genre":
            conditions.append("genre = ?")
            params.append(value)
        elif key == "artist":
            conditions.append("artist = ?")
            params.append(value)
        elif key == "album":
            conditions.append("album = ?")
            params.append(value)
        elif key == "year_min":
            conditions.append("year >= ?")
            params.append(int(value))
        elif key == "year_max":
            conditions.append("year <= ?")
            params.append(int(value))
        elif key == "rating_min":
            conditions.append("rating >= ?")
            params.append(int(value))
        elif key == "play_count_min":
            conditions.append("play_count >= ?")
            params.append(int(value))
    where = " AND ".join(conditions) if conditions else "1=1"
    return f"SELECT * FROM songs WHERE {where} ORDER BY artist, album, track_number", params


def evaluate_rules(db: Database, rules: dict) -> list[Song]:
    query, params = build_query(rules)
    rows = db.conn.execute(query, params).fetchall()
    return [db._row_to_song(r) for r in rows]
