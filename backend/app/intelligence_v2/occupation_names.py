"""Shared normalization for occupation names used by reference engines."""

from __future__ import annotations

import json


ROLE_ALIASES: dict[str, str] = {
    "backend developer": "Software Developer",
    "backend engineer": "Software Developer",
    "python developer": "Software Developer",
    "python engineer": "Software Developer",
    "full stack developer": "Software Developer",
    "full-stack developer": "Software Developer",
    "full stack engineer": "Software Developer",
    "fullstack developer": "Software Developer",
    "frontend developer": "Software Developer",
    "frontend engineer": "Software Developer",
}


def resolve_role_alias(role_name: str | None) -> tuple[str | None, str | None]:
    """Resolve common non-standard role names to closest O*NET standard.

    Returns (resolved_standard_role, alias_notice_or_none).
    """
    if not role_name:
        return None, None
    cleaned = " ".join(role_name.split()).casefold()
    target = ROLE_ALIASES.get(cleaned)
    if target:
        notice = f"No exact O*NET/ESCO occupation match for '{role_name}'; showing verified reference data for '{target}'."
        return target, notice
    return role_name, None


def normalize_occupation_name(value: str) -> str:
    """Normalize casing, whitespace, and a simple plural on the final word."""
    words = " ".join(value.split()).casefold().split()
    if words:
        final_word = words[-1]
        if final_word.endswith("ies") and len(final_word) > 3:
            words[-1] = f"{final_word[:-3]}y"
        elif final_word.endswith("s") and not final_word.endswith(("ss", "us", "is")):
            words[-1] = final_word[:-1]
    return " ".join(words)


def occupation_label_matches(value: str, preferred_label: str, aliases: str | None = None) -> bool:
    """Match a normalized role exactly against a title or serialized aliases."""
    normalized_value = normalize_occupation_name(value)
    if normalize_occupation_name(preferred_label) == normalized_value:
        return True
    if not aliases:
        return False

    try:
        parsed_aliases = json.loads(aliases)
    except json.JSONDecodeError:
        parsed_aliases = aliases.splitlines()
    if isinstance(parsed_aliases, str):
        parsed_aliases = [parsed_aliases]
    if not isinstance(parsed_aliases, list):
        return False
    return any(
        isinstance(alias, str)
        and normalize_occupation_name(alias) == normalized_value
        for alias_group in parsed_aliases
        for alias in alias_group.splitlines()
    )
