from typing import Optional
from soundwave.library.database.database import Database, Song


RULE_FIELDS = {
    "genre": {"label": "Género", "op": "="},
    "artist": {"label": "Artista", "op": "="},
    "album": {"label": "Álbum", "op": "="},
    "year_min": {"label": "Año mínimo", "op": ">="},
    "year_max": {"label": "Año máximo", "op": "<="},
    "rating_min": {"label": "Valoración mínima", "op": ">="},
    "play_count_min": {"label": "Reproducciones mínimas", "op": ">="},
    "recent": {"label": "Recientes", "op": "LIMIT"},
    "most_played": {"label": "Más Escuchadas", "op": "LIMIT"},
}


def build_query(rules: dict) -> tuple[str, list]:
    conditions = []
    params = []
    order_by = "artist COLLATE NOCASE, album COLLATE NOCASE, track_number"
    limit = ""

    for key, value in rules.items():
        if value is None or value == "":
            continue
        if key == "genre":
            conditions.append("genre COLLATE NOCASE = ?")
            params.append(value)
        elif key == "artist":
            conditions.append("artist COLLATE NOCASE = ?")
            params.append(value)
        elif key == "album":
            conditions.append("album COLLATE NOCASE = ?")
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
        elif key == "recent":
            if value:
                order_by = "added_at DESC"
                limit = " LIMIT 50"
        elif key == "most_played":
            if value:
                conditions.append("play_count > 0")
                order_by = "play_count DESC, last_played DESC"
                limit = " LIMIT 50"

    where = " AND ".join(conditions) if conditions else "1=1"
    query = f"SELECT * FROM songs WHERE {where} ORDER BY {order_by}{limit}"
    return query, params


def evaluate_rules(db: Database, rules: dict) -> list[Song]:
    query, params = build_query(rules)
    rows = db.conn.execute(query, params).fetchall()
    return [db._row_to_song(r) for r in rows]
