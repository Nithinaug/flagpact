from typing import Any

RED = "red"
AMBER = "amber"
GREEN = "green"


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def lookup(value: Any, path: str) -> tuple[bool, Any]:
    node = value
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return False, None
    return True, node


def static_check(contract: dict[str, Any] | None, value: dict[str, Any]) -> tuple[str, str]:
    if contract is None:
        return AMBER, "no contract recorded for this version"
    for read in contract["reads"]:
        present, found = lookup(value, read["path"])
        if not present:
            if read["has_default"]:
                continue
            return RED, f"required path '{read['path']}' is missing"
        expected = read["type"].split("|")
        if "missing" in expected and len(expected) == 1:
            continue
        if type_name(found) not in expected:
            return RED, f"path '{read['path']}' is {type_name(found)}, contract has {read['type']}"
    return AMBER, "no static break found, replay not run"
