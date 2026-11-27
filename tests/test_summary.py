import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("summary", ROOT / "scripts" / "summary.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def report(breaks=2):
    return {
        "status": "fail" if breaks else "pass",
        "flag": "home_banner",
        "breaks": breaks,
        "versions": [
            {"version": "1.0.0", "result": "breaks" if breaks else "safe", "reason": "replay failed"},
            {"version": "3.0.0", "result": "safe", "reason": "replay passed"},
            {"version": "none", "result": "not_checked", "reason": "no recorded behaviour"},
        ],
        "notices": ["A percentage rollout applies."],
        "fix": {"keep_below": "3.0.0"} if breaks else None,
    }


def test_a_failing_report_lists_each_version_and_the_fix():
    text = summary.render(report(2))
    assert "2 of 2 app versions would break" in text
    assert "| 1.0.0 | Breaks |  | replay failed |" in text
    assert "| no app_version | Not checked |" in text
    assert "Note: A percentage rollout applies." in text
    assert "keep versions below 3.0.0" in text


def test_a_passing_report_says_nothing_would_break():
    text = summary.render(report(0))
    assert "No app version would break." in text and "Suggested fix" not in text


def test_an_error_report_explains_the_failure():
    text = summary.render({"status": "error", "error": "missing environment variable FLAGSMITH_API_URL"})
    assert "could not run" in text and "FLAGSMITH_API_URL" in text
