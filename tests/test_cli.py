import json
import pathlib

from flagpact.cli import main

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCUMENT = json.loads((ROOT / "demo" / "environment.json").read_text())
CONFIG = str(ROOT / "flagpact.json")
BREAKING = {"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}


class StubAdmin:
    def document(self):
        return DOCUMENT


def run(argv, capsys, admin=StubAdmin()):
    code = main(argv, admin)
    return code, capsys.readouterr()


def test_breaking_change_exits_one_with_a_plain_report(capsys):
    code, out = run(["check", "--value", json.dumps(BREAKING), "--config", CONFIG], capsys)
    assert code == 1
    assert "2 of 3 app versions would break" in out.out
    assert "1.0.0" in out.out and "BREAKS" in out.out
    assert "keep versions below 3.0.0" in out.out


def test_json_report_shape(capsys):
    code, out = run(["check", "--value", json.dumps(BREAKING), "--config", CONFIG, "--json"], capsys)
    report = json.loads(out.out)
    assert code == 1 and report["status"] == "fail"
    assert report["breaks"] == 2 and report["safe"] == 1 and report["not_checked"] == 1
    assert report["fix"]["keep_below"] == "3.0.0"
    assert [v["result"] for v in report["versions"]] == ["breaks", "breaks", "safe", "not_checked"]
    assert "key" not in json.dumps(report).lower().replace("keep", "")


def test_unchanged_value_exits_zero(capsys):
    live = json.dumps({"title": "Sale on now", "heading": "Sale on now", "cta": {"text": "Shop", "label": "Shop"}})
    code, out = run(["check", "--value", live, "--config", CONFIG, "--json"], capsys)
    report = json.loads(out.out)
    assert code == 0 and report["status"] == "pass" and report["breaks"] == 0


def test_value_can_come_from_a_file(capsys, tmp_path):
    path = tmp_path / "value.json"
    path.write_text(json.dumps(BREAKING))
    code, _ = run(["check", "--value", str(path), "--config", CONFIG], capsys)
    assert code == 1


def test_bad_json_exits_two(capsys):
    code, out = run(["check", "--value", "{nope", "--config", CONFIG], capsys)
    assert code == 2 and "flagpact:" in out.err


def test_missing_credentials_exit_two(capsys, monkeypatch):
    monkeypatch.delenv("FLAGSMITH_API_URL", raising=False)
    monkeypatch.delenv("FLAGSMITH_ENV_SERVER_KEY", raising=False)
    code, out = run(["check", "--value", "{}", "--config", CONFIG], capsys, admin=None)
    assert code == 2 and "FLAGSMITH_API_URL" in out.err


def test_missing_credentials_in_json_mode_reports_an_error_status(capsys, monkeypatch):
    monkeypatch.delenv("FLAGSMITH_API_URL", raising=False)
    code, out = run(["check", "--value", "{}", "--config", CONFIG, "--json"], capsys, admin=None)
    assert code == 2 and json.loads(out.out)["status"] == "error"


def test_report_shows_how_many_users_are_at_risk(capsys):
    code, out = run(["check", "--value", json.dumps(BREAKING), "--config", CONFIG, "--json"], capsys)
    report = json.loads(out.out)
    assert report["at_risk"] == {"share": 61, "users": 114200}
    assert [v.get("users") for v in report["versions"]] == [41200, 73000, 65500, 7400]
    code, out = run(["check", "--value", json.dumps(BREAKING), "--config", CONFIG], capsys)
    assert "At risk: 61% of sessions, about 114,200 users" in out.out


def test_safe_change_reports_no_risk_line(capsys):
    safe = DOCUMENT["feature_states"][0]["feature_state_value"]
    code, out = run(["check", "--value", safe, "--config", CONFIG], capsys)
    assert code == 0 and "At risk" not in out.out


def test_report_carries_the_fix_an_agent_can_apply(capsys):
    code, out = run(["check", "--value", json.dumps(BREAKING), "--config", CONFIG, "--json"], capsys)
    fix = json.loads(out.out)["fix"]
    assert fix["segment"] == "flagpact/home_banner/3.0.0"
    condition = fix["rules"][0]["rules"][0]["conditions"][0]
    assert fix["rule"] == fix["rules"][0] and fix["rule"]["type"] == "ALL"
    assert condition == {"operator": "LESS_THAN", "property": "app_version", "value": "3.0.0:semver"}
    assert fix["keep_value"] == json.loads(DOCUMENT["feature_states"][0]["feature_state_value"])
