import json
import pathlib

from flagpact.contracts import load_contracts
from flagpact.matrix import AppVersion, build_matrix
from flagpact.resolver import patch_default, resolve
from flagpact.verdict import AMBER, GREEN, RED, static_check

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCUMENT = json.loads((ROOT / "demo" / "environment.json").read_text())
NEW = {"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}
VERSIONS = [AppVersion(f"{n}.0.0", str(ROOT / "demo" / f"v{n}")) for n in (1, 2, 3)]


def contract_for(version):
    return next(c for c in load_contracts(str(ROOT / "contracts"), "home_banner") if c["app_version"] == version)


def test_resolve_returns_patched_default():
    patched = patch_default(DOCUMENT, "home_banner", NEW)
    assert resolve(patched, "home_banner", "1.0.0") == NEW
    assert resolve(patched, "home_banner", None) == NEW


def test_static_red_when_required_path_removed():
    state, reason = static_check(contract_for("1.0.0"), NEW)
    assert state == RED and "title" in reason


def test_static_optional_path_missing_is_not_red():
    value = {"heading": "h", "cta": {"label": "l"}}
    assert static_check(contract_for("3.0.0"), value)[0] == AMBER


def test_static_type_change_is_red():
    state, reason = static_check(contract_for("1.0.0"), {"title": 5})
    assert state == RED and "number" in reason


def test_static_no_contract_is_amber():
    assert static_check(None, NEW)[0] == AMBER


def test_matrix_without_replay_shows_static_states():
    cells = build_matrix(DOCUMENT, "home_banner", NEW, VERSIONS, str(ROOT / "contracts"), run_replay=False)
    assert [c.state for c in cells] == [RED, RED, AMBER]


def test_matrix_with_replay_is_final():
    cells = build_matrix(DOCUMENT, "home_banner", NEW, VERSIONS, str(ROOT / "contracts"))
    assert [c.state for c in cells] == [RED, RED, GREEN]
    assert all(c.reason for c in cells)
