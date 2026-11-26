import json

from flagpact.contracts import content_hash, load_contracts, save_contract


def contract(version="1.0.0"):
    return {"flag": "home_banner", "app_version": version, "recorded_from": "t.py", "reads": []}


def test_save_and_load_round_trip(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("a = 1")
    path = save_contract(str(tmp_path / "contracts"), contract(), [str(src)])
    assert path.parent.name == "home_banner"
    assert path.name == f"1.0.0-{content_hash([str(src)])}.json"
    assert load_contracts(str(tmp_path / "contracts"), "home_banner") == [contract()]


def test_code_change_makes_a_new_contract(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("a = 1")
    root = str(tmp_path / "contracts")
    save_contract(root, contract(), [str(src)])
    src.write_text("a = 2")
    save_contract(root, contract(), [str(src)])
    assert len(load_contracts(root, "home_banner")) == 2


def test_unknown_flag_has_no_contracts(tmp_path):
    assert load_contracts(str(tmp_path), "nope") == []
