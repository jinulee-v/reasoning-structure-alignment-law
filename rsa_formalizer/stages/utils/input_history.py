"""Lossless JSON history compaction, independent of the input schema or domain."""


def compact(value):
    """Share object keys across rows without losing omitted-versus-null fields."""
    if isinstance(value, list):
        if value and all(isinstance(row, dict) for row in value):
            columns = sorted(set().union(*(row.keys() for row in value)))
            return {"$table": {
                "columns": columns,
                "present": [[key in row for key in columns] for row in value],
                "rows": [[compact(row.get(key)) for key in columns] for row in value],
            }}
        return [compact(item) for item in value]
    if isinstance(value, dict):
        if "$table" in value or "$object" in value:
            return {"$object": [[key, compact(item)] for key, item in value.items()]}
        return {key: compact(item) for key, item in value.items()}
    return value


def expand(value):
    """Decode the history representation, including escaped reserved keys."""
    if isinstance(value, list):
        return [expand(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"$table"}:
            table = value["$table"]
            return [{key: expand(item)
                     for key, item, present in zip(table["columns"], row, mask) if present}
                    for row, mask in zip(table["rows"], table["present"])]
        if set(value) == {"$object"}:
            return {key: expand(item) for key, item in value["$object"]}
        return {key: expand(item) for key, item in value.items()}
    return value
