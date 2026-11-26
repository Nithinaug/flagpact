import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from .contracts import load_contracts
from .replay import replay
from .resolver import patch_default, resolve
from .verdict import AMBER, GREEN, RED, static_check


@dataclass
class AppVersion:
    version: str
    directory: str


@dataclass
class Cell:
    version: str
    state: str
    reason: str
    value: dict[str, Any]


def build_matrix(document: dict[str, Any], flag: str, new_value: dict[str, Any], versions: list[AppVersion],
                 contracts_root: str, run_replay: bool = True) -> list[Cell]:
    patched = patch_default(document, flag, new_value)
    cells = []
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "patched.json")
        with open(path, "w") as handle:
            json.dump(patched, handle)
        statics = []
        for app in versions:
            value = resolve(patched, flag, app.version)
            contracts = load_contracts(contracts_root, flag)
            contract = next((c for c in reversed(contracts) if c["app_version"] == app.version), None)
            statics.append((app, value, *static_check(contract, value)))
        if run_replay:
            with ThreadPoolExecutor(max_workers=len(versions) or 1) as pool:
                results = list(pool.map(lambda item: replay(item[0].directory, path, item[0].version), statics))
        else:
            results = [None] * len(statics)
        for (app, value, state, reason), result in zip(statics, results):
            if result is not None:
                state, reason = (GREEN, "replay passed") if result.passed else (RED, "replay failed")
            cells.append(Cell(app.version, state, reason, value))
    return cells
