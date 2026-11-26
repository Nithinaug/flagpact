import json
import os
import tempfile
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
        for app in versions:
            value = resolve(patched, flag, app.version)
            contracts = load_contracts(contracts_root, flag)
            contract = next((c for c in reversed(contracts) if c["app_version"] == app.version), None)
            state, reason = static_check(contract, value)
            if run_replay:
                result = replay(app.directory, path, app.version)
                if result.passed:
                    state, reason = GREEN, "replay passed"
                else:
                    state, reason = RED, "replay failed"
            cells.append(Cell(app.version, state, reason, value))
    return cells
