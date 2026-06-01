"""A Sigma-compatible YAML rule engine.

Supports the subset of real Sigma syntax used by ``data/sigma/*.yml``:

- ``detection`` blocks made of named selections (``selection``, ``filter_*``,
  etc), each a mapping of ``field`` or ``field|modifier`` to a scalar or list
  of expected values (list == logical OR).
- Modifiers: ``contains``, ``endswith``, ``startswith``, ``gt``, ``lt``.
- A ``condition`` string combining named blocks with ``and`` / ``or`` /
  ``not`` (evaluated as a boolean expression over the block match results).
- An optional top-level ``correlation`` block (multi-event; evaluated by
  ``detection_core.correlation``, not here — ``match_single`` only decides
  whether *this* event satisfies the rule's single-event predicate, which
  for a pure-correlation rule is just ``condition: correlation``).

Field resolution first checks the ``CanonicalEvent`` model directly (via a
small alias table for Sigma field names that don't map 1:1 onto our schema,
e.g. ``image`` -> ``process``), then falls back to the original raw payload
preserved on ``event.raw``, matching keys loosely (case/underscore
insensitive) so PascalCase source fields like ``EventID`` line up with
snake_case Sigma field names like ``event_id``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from aegis_common.schema.events import CanonicalEvent

logger = logging.getLogger("aegis.detection.sigma")

# Sigma field names that don't correspond 1:1 to a CanonicalEvent attribute
# name. Checked before the generic attribute/raw-payload fallback.
FIELD_ALIASES: dict[str, str] = {
    "image": "process",
    "parent_image": "parent_process",
    "target_filename": "file_path",
    "dns_query": "domain",
    "attachment_name": "file_path",
    "attachment_hash": "file_hash",
    "mitre_techniques": "technique_ids",
    "technique_id": "technique_ids",
}

# Fields that need a specific raw-payload key (or don't survive the generic
# "strip underscores, lowercase" fuzzy match against the raw key).
RAW_FIELD_ALIASES: dict[str, str] = {
    "zeek_log_type": "log_type",
    "k8s_resource": "resource",
    "k8s_verb": "verb",
}


def data_dir() -> Path:
    return Path(os.getenv("AEGIS_DATA_DIR", "./data"))


def load_rules() -> list[dict[str, Any]]:
    rules_dir = data_dir() / "sigma"
    rules: list[dict[str, Any]] = []
    if not rules_dir.exists():
        logger.warning("sigma_rules_dir_missing path=%s", rules_dir)
        return rules
    for path in sorted(rules_dir.glob("*.yml")):
        try:
            rule = yaml.safe_load(path.read_text())
            if not rule:
                continue
            rule["_file"] = path.name
            rules.append(rule)
        except Exception:
            logger.exception("failed_to_load_sigma_rule file=%s", path)
    return rules


def _raw_lookup(raw: dict[str, Any], field: str) -> Any:
    if field in raw:
        return raw[field]
    target = field.replace("_", "").lower()
    for key, value in raw.items():
        if key.replace("_", "").lower() == target:
            return value
    return None


def _get_field(event: CanonicalEvent, field: str) -> Any:
    field = field.lower()

    if field == "dns_query_length":
        return len(event.domain) if event.domain else 0
    if field == "alert_category":
        return (event.raw.get("alert") or {}).get("category")
    if field == "alert_severity":
        return (event.raw.get("alert") or {}).get("severity")

    attr_name = FIELD_ALIASES.get(field, field)
    if hasattr(event, attr_name):
        value = getattr(event, attr_name)
        if value not in (None, "", []):
            return value

    raw = event.raw or {}
    raw_key = RAW_FIELD_ALIASES.get(field, field)
    value = _raw_lookup(raw, raw_key)
    if value is not None:
        return value
    return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _match_value(actual: Any, expected: Any, modifier: str) -> bool:
    if actual is None:
        return False
    expected_list = expected if isinstance(expected, list) else [expected]

    if modifier == "contains":
        if isinstance(actual, (list, tuple, set)):
            actual_strs = [str(a).lower() for a in actual]
            return any(str(needle).lower() in actual_strs for needle in expected_list)
        actual_str = str(actual).lower()
        return any(str(needle).lower() in actual_str for needle in expected_list)
    if modifier == "endswith":
        actual_str = str(actual).lower()
        return any(actual_str.endswith(str(needle).lower()) for needle in expected_list)
    if modifier == "startswith":
        actual_str = str(actual).lower()
        return any(actual_str.startswith(str(needle).lower()) for needle in expected_list)
    if modifier in ("gt", "lt", "gte", "lte"):
        try:
            actual_num = float(actual)
            expected_num = float(expected_list[0])
        except (TypeError, ValueError):
            return False
        if modifier == "gt":
            return actual_num > expected_num
        if modifier == "lt":
            return actual_num < expected_num
        if modifier == "gte":
            return actual_num >= expected_num
        return actual_num <= expected_num

    # No modifier: equality-against-any, with list/bool-aware coercion.
    if isinstance(actual, (list, tuple, set)):
        actual_strs = [str(a).lower() for a in actual]
        return any(str(needle).lower() in actual_strs for needle in expected_list)
    if isinstance(actual, bool):
        return any(_to_bool(needle) == actual for needle in expected_list)
    actual_str = str(actual).lower()
    return any(str(needle).lower() == actual_str for needle in expected_list)


def _evaluate_block(block: Any, event: CanonicalEvent) -> tuple[bool, dict[str, Any]]:
    if not isinstance(block, dict):
        return False, {}
    evidence: dict[str, Any] = {}
    for raw_key, expected in block.items():
        field, _, modifier = str(raw_key).partition("|")
        actual = _get_field(event, field)
        if not _match_value(actual, expected, modifier):
            return False, {}
        evidence[field] = actual
    return True, evidence


def _evaluate_condition(condition: str, results: dict[str, bool]) -> bool:
    condition = (condition or "").strip()
    if not condition:
        return results.get("selection", False)
    try:
        return bool(eval(condition, {"__builtins__": {}}, dict(results)))  # noqa: S307
    except Exception:
        logger.warning("sigma_condition_eval_failed condition=%s", condition)
        return all(v for k, v in results.items() if not k.startswith("filter"))


def match_single(rule: dict[str, Any], event: CanonicalEvent) -> tuple[bool, dict[str, Any]]:
    """Evaluate the single-event predicate of a rule against ``event``.

    For a rule with a top-level ``correlation`` block whose condition is
    literally ``correlation``, this just returns ``True`` (the caller is
    responsible for then invoking the correlation engine to make the final
    call). For every other rule this fully evaluates the ``detection``
    selection/filter blocks and condition string.
    """

    detection = rule.get("detection", {}) or {}
    condition = detection.get("condition", "selection")

    block_names = [k for k in detection.keys() if k != "condition"]
    results: dict[str, bool] = {}
    evidence: dict[str, Any] = {}
    for name in block_names:
        matched, block_evidence = _evaluate_block(detection[name], event)
        results[name] = matched
        if matched:
            evidence[name] = block_evidence

    # The multi-event ``correlation`` block (if present) is evaluated
    # separately by ``detection_core.correlation`` after this single-event
    # gate passes. Treat its token as provisionally satisfied here so a
    # condition like ``selection and correlation`` still exercises the
    # ``selection`` gate rather than always failing.
    results.setdefault("correlation", True)

    matched = _evaluate_condition(condition, results)
    return matched, {"matched_blocks": evidence, "condition": condition}
