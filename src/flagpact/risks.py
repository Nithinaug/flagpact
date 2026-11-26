from typing import Any


def _has_split(node: Any) -> bool:
    if isinstance(node, dict):
        if node.get("operator") == "PERCENTAGE_SPLIT":
            return True
        return any(_has_split(value) for value in node.values())
    if isinstance(node, list):
        return any(_has_split(item) for item in node)
    return False


def detect(document: dict[str, Any], flag: str) -> dict[str, Any]:
    multivariate = any(
        state["feature"]["name"] == flag and state.get("multivariate_feature_state_values")
        for state in document.get("feature_states", [])
    )
    percentage: list[str] = []
    for segment in document.get("project", {}).get("segments", []):
        overrides = [f for f in segment.get("feature_states", []) if f["feature"]["name"] == flag]
        if not overrides:
            continue
        if _has_split(segment.get("rules", [])):
            percentage.append(segment["name"])
        if any(f.get("multivariate_feature_state_values") for f in overrides):
            multivariate = True
    identities = sum(
        1
        for override in document.get("identity_overrides") or []
        if any(f["feature"]["name"] == flag for f in override.get("identity_features", []))
    )
    return {"multivariate": multivariate, "percentage": percentage, "identity_overrides": identities}


def notices(document: dict[str, Any], flag: str) -> list[str]:
    found = detect(document, flag)
    lines = []
    if found["percentage"]:
        lines.append("A percentage rollout applies to this flag, so versions in that group are only partly checked.")
    if found["multivariate"]:
        lines.append("This flag has variations, so each version is checked against one variation only.")
    if found["identity_overrides"]:
        lines.append(f"{found['identity_overrides']} identities have their own value for this flag and are not covered.")
    return lines


def partial(document: dict[str, Any], flag: str) -> bool:
    found = detect(document, flag)
    return bool(found["percentage"] or found["multivariate"])
