"""Role -> allowed-module enforcement. Config-driven, not real DB grants
(doc section 8's RBAC intent, simplified for a single-tenant demo)."""
from __future__ import annotations

import functools

import yaml

from config.settings import RBAC_CONFIG_PATH


@functools.lru_cache(maxsize=1)
def _rbac_config() -> dict:
    with open(RBAC_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def allowed_modules(role: str) -> set[str]:
    roles = _rbac_config()["roles"]
    if role not in roles:
        role = _rbac_config()["default_role"]
    return set(roles[role]["modules"])


def filter_tables_by_role(table_to_module: dict[str, str], role: str) -> set[str]:
    """table_to_module: {table_name: module_name}. Returns the subset of table
    names whose module is in the role's allowed modules."""
    mods = allowed_modules(role)
    return {t for t, m in table_to_module.items() if m in mods}
