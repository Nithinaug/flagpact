import hashlib
import json
import pathlib
from typing import Any


def content_hash(sources: list[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(sources):
        digest.update(pathlib.Path(path).read_bytes())
    return digest.hexdigest()[:8]


def save_contract(root: str, contract: dict[str, Any], sources: list[str]) -> pathlib.Path:
    target = pathlib.Path(root) / contract["flag"] / f"{contract['app_version']}-{content_hash(sources)}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(contract, indent=2) + "\n")
    return target


def load_contracts(root: str, flag: str) -> list[dict[str, Any]]:
    folder = pathlib.Path(root) / flag
    if not folder.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
