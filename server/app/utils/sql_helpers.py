"""
Shared helpers for building dynamic UPDATE ... SET clauses safely.

Column names can never come from raw user input in SQL text via string
interpolation. This module centralizes the pattern used across the app:
  1. Restrict incoming field names to an explicit allow-list.
  2. Validate every surviving key against a strict identifier pattern
     (defense in depth, in case the allow-list itself is ever misconfigured).
  3. Build the "col = :col" fragments from those validated keys only.

Using one shared, well-tested helper instead of re-implementing this in
every route/service also avoids duplicating the same 3-4 lines of logic
in multiple files.
"""
import re
from typing import Any, Mapping

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def build_safe_set_clause(
    data: Mapping[str, Any],
    allowed_fields: set[str] | list[str],
) -> tuple[str, dict[str, Any]]:
    """
    Build a `col1 = :col1, col2 = :col2` SET-clause fragment from `data`,
    restricted to `allowed_fields` and validated as safe SQL identifiers.

    Returns (set_clause_sql, bind_params). Raises ValueError if nothing
    in `data` is eligible, so callers don't accidentally run a no-op
    UPDATE ... SET WHERE ... statement.
    """
    allowed = set(allowed_fields)
    safe_items = {
        key: value
        for key, value in data.items()
        if key in allowed and _SAFE_IDENTIFIER.match(key)
    }
    if not safe_items:
        raise ValueError("No valid fields to update")

    set_clause = ", ".join(f"{key} = :{key}" for key in safe_items)
    return set_clause, safe_items
