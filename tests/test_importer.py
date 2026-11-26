import json
import os
import pathlib
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from flagpact import importer
from flagpact.cli import main
from flagpact.contracts import load_contracts
from flagpact.importer import ScanError, parse_github_url, resolve_local, scan_directory, scan_source
from flagpact.server import make_handler
from flagpact.service import Service

ROOT = pathlib.Path(__file__).resolve().parents[1]


def write(base, name, text, raw=False):
    if not raw and name.endswith(".py") and ("config(" in text or "get_feature_value" in text):
        text = "import flagpact\n" + text
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def reads_of(result, flag="home_banner"):
    entry = next(f for f in result["flags"] if f["flag"] == flag)
    return {r["path"]: r for r in entry["reads"]}


def test_demo_scan_matches_the_recorded_contracts():
    result = scan_directory(ROOT / "demo")
    reads = reads_of(result)
    assert [v["version"] for v in result["versions"]] == ["1.0.0", "2.0.0", "3.0.0"]
    for contract in load_contracts(str(ROOT / "contracts"), "home_banner"):
        version = contract["app_version"]
        for read in contract["reads"]:
            found = reads[read["path"]]
            bucket = "default_in" if read["has_default"] else "required_in"
            assert version in found[bucket], (version, read["path"])


def test_draft_config_lists_flag_and_versions():
    draft = scan_directory(ROOT / "demo")["draft"]
    assert draft["flag"] == "home_banner" and draft["trait"] == "app_version"
    assert [v["directory"] for v in draft["versions"]] == ["v1", "v2", "v3"]


def test_scan_follows_aliases_and_chained_get(tmp_path):
    write(tmp_path, "app.py", '''
import json
APP_VERSION = "4.1.0"

def banner(sdk):
    raw = json.loads(sdk.get_feature_value("promo"))
    cta = raw["cta"]
    label = cta["label"]
    text = raw.get("cta", {}).get("text")
    sub = raw.get("sub", "")
    return label, text, sub
''')
    reads = reads_of(scan_directory(tmp_path), "promo")
    assert sorted(reads) == ["cta.label", "cta.text", "sub"]
    assert reads["cta.label"]["required"] and not reads["sub"]["required"]


def test_parent_paths_are_dropped_when_a_child_is_read(tmp_path):
    write(tmp_path, "app.py", 'def f(c):\n    cfg = c.config("x")\n    return cfg["a"]["b"], cfg["a"]\n')
    assert sorted(reads_of(scan_directory(tmp_path), "x")) == ["a.b"]


def test_function_scopes_do_not_leak(tmp_path):
    write(tmp_path, "app.py", 'def f(c):\n    cfg = c.config("x")\n\ndef g(cfg):\n    return cfg["leak"]\n')
    assert reads_of(scan_directory(tmp_path), "x") == {}


def test_other_languages_list_the_flag_but_not_the_fields(tmp_path):
    write(tmp_path, "src/banner.ts", 'const raw = flagsmith.getValue("home_banner");\n')
    result = scan_directory(tmp_path)
    flag = result["flags"][0]
    assert flag["flag"] == "home_banner" and flag["reads"] == [] and flag["languages"] == ["other"]
    assert any("other languages" in line for line in result["needs_review"])


def test_no_flags_gives_no_draft(tmp_path):
    write(tmp_path, "app.py", "print('hi')\n")
    result = scan_directory(tmp_path)
    assert result["draft"] is None and result["flags"] == []


def test_package_version_is_marked_as_a_guess(tmp_path):
    write(tmp_path, "app.py", 'def f(c):\n    return c.config("x")["a"]\n')
    write(tmp_path, "pyproject.toml", '[project]\nversion = "2.3.4"\n')
    result = scan_directory(tmp_path)
    assert result["versions"][0]["version"] == "2.3.4" and result["versions"][0]["guessed"]
    assert any("package file" in line for line in result["needs_review"])


def test_broken_python_is_reported_not_fatal(tmp_path):
    write(tmp_path, "bad.py", "import flagpact\ndef (:\n")
    write(tmp_path, "good.py", 'def f(c):\n    return c.config("x")["a"]\n')
    result = scan_directory(tmp_path)
    assert any("bad.py" in n for n in result["notes"]) and result["flags"][0]["flag"] == "x"


def test_scan_never_runs_the_code(tmp_path):
    marker = tmp_path / "ran"
    write(tmp_path, "app.py", f'open({str(marker)!r}, "w").write("x")\nraise SystemExit(1)\n')
    scan_directory(tmp_path)
    assert not marker.exists()


def test_symlinks_are_not_followed(tmp_path):
    outside = tmp_path / "outside"
    write(outside, "secret.py", 'def f(c):\n    return c.config("leaked")["a"]\n')
    project = tmp_path / "project"
    project.mkdir()
    (project / "link.py").symlink_to(outside / "secret.py")
    (project / "linkdir").symlink_to(outside, target_is_directory=True)
    assert scan_directory(project)["flags"] == []


def test_large_files_and_skipped_folders(tmp_path):
    write(tmp_path, "big.py", "x = 1\n" * 200000)
    write(tmp_path, "node_modules/lib.py", 'def f(c):\n    return c.config("hidden")["a"]\n')
    result = scan_directory(tmp_path)
    assert result["flags"] == [] and any("big.py" in n for n in result["notes"])


def test_github_urls_are_strict():
    assert parse_github_url("https://github.com/owner/repo") == "https://github.com/owner/repo.git"
    assert parse_github_url("github.com/owner/repo.git") == "https://github.com/owner/repo.git"
    assert parse_github_url("https://github.com/o/r.js/") == "https://github.com/o/r.js.git"
    for bad in [
        "https://evil.com/o/r",
        "https://github.com.evil.com/o/r",
        "https://user:pw@github.com/o/r",
        "https://github.com/o/r/tree/main",
        "https://github.com/o/..",
        "https://github.com/o",
        "https://github.com/-o/r",
        "https://github.com/o/r?x=1",
    ]:
        with pytest.raises(ScanError):
            parse_github_url(bad)


def ok_runner(files):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        target = pathlib.Path(command[-1])
        for name, text in files.items():
            write(target, name, text)
        return subprocess.CompletedProcess(command, 0, "", "")

    run.calls = calls
    return run


def test_clone_is_shallow_hardened_and_removed(monkeypatch):
    runner = ok_runner({"app.py": 'def f(c):\n    return c.config("x")["a"]\n'})
    result = scan_source("https://github.com/owner/repo", runner)
    command, kwargs = runner.calls[0]
    assert command[0] == "git" and "--depth" in command and "--no-recurse-submodules" in command
    assert "protocol.allow=never" in command and "core.symlinks=false" in command
    assert command[command.index("--") + 1] == "https://github.com/owner/repo.git"
    assert kwargs["timeout"] == importer.CLONE_TIMEOUT and "shell" not in kwargs
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0" and kwargs["env"]["GIT_CONFIG_GLOBAL"] == os.devnull
    assert not any(key.startswith(("AWS", "GITHUB", "SSH")) for key in kwargs["env"])
    assert not pathlib.Path(command[-1]).exists()
    assert result["kind"] == "github" and result["source"] == "https://github.com/owner/repo"
    assert result["flags"][0]["flag"] == "x"


def test_failed_and_slow_clones_are_reported():
    def fail(command, **kwargs):
        return subprocess.CompletedProcess(command, 128, "", "fatal: could not read Username")

    with pytest.raises(ScanError, match="public"):
        scan_source("https://github.com/owner/private", fail)

    def slow(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 60)

    with pytest.raises(ScanError, match="seconds"):
        scan_source("https://github.com/owner/slow", slow)


@pytest.mark.parametrize("source", [
    "", "   ", "ssh://git@github.com/o/r", "git@github.com:o/r.git", "file:///etc", "ext::sh -c id",
    "http://github.com/o/r", "https://gitlab.com/o/r", "a\nb", "x" * 400,
])
def test_unsupported_sources_are_refused(source):
    with pytest.raises(ScanError):
        scan_source(source, ok_runner({}))


def test_local_folder_checks(tmp_path):
    assert resolve_local(str(tmp_path)) == tmp_path.resolve()
    for bad in ["/", "/etc", "/proc/self", str(pathlib.Path.home()), str(tmp_path / "missing"), str(tmp_path / "file.txt")]:
        (tmp_path / "file.txt").write_text("x")
        with pytest.raises(ScanError):
            resolve_local(bad)


def test_local_scan_reports_folder_name(tmp_path):
    write(tmp_path, "app.py", 'def f(c):\n    return c.config("x")["a"]\n')
    result = scan_source(str(tmp_path))
    assert result["kind"] == "local" and result["source"] == tmp_path.name


def test_cli_import_prints_and_writes_a_draft(tmp_path, capsys):
    assert main(["import", str(ROOT / "demo")]) == 0
    assert "home_banner" in capsys.readouterr().out
    out = tmp_path / "flagpact.json"
    assert main(["import", str(ROOT / "demo"), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["flag"] == "home_banner"
    assert main(["import", str(ROOT / "demo"), "--out", str(out)]) == 2
    assert "already exists" in capsys.readouterr().err


def test_cli_import_json_and_empty_folder(tmp_path, capsys):
    assert main(["import", str(ROOT / "demo"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["draft"]["flag"] == "home_banner"
    assert main(["import", str(tmp_path)]) == 1


class StubAdmin:
    def document(self):
        return {}


@pytest.fixture
def base():
    service = Service(StubAdmin(), str(ROOT / "flagpact.json"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def post(base, body, headers=None):
    request = urllib.request.Request(base + "/api/import", data=json.dumps(body).encode(), method="POST")
    for key, value in (headers if headers is not None else {"Content-Type": "application/json"}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_import_route_scans_a_github_repository(base, monkeypatch):
    from flagpact import server as server_module
    runner = ok_runner({"app.py": 'def f(c):\n    return c.config("x")["a"]\n'})
    monkeypatch.setattr(server_module, "scan_source", lambda s, github_only=False: scan_source(s, runner, github_only))
    status, body = post(base, {"source": "https://github.com/owner/repo"})
    assert status == 200 and body["draft"]["flag"] == "x"


def test_import_route_refuses_local_folders(base):
    status, body = post(base, {"source": str(ROOT / "demo")})
    assert status == 409 and "GitHub" in body["error"]


def test_import_route_refuses_foreign_requests(base):
    assert post(base, {"source": str(ROOT / "demo")}, headers={})[0] == 403
    assert post(base, {"source": str(ROOT / "demo")}, headers={"Content-Type": "text/plain"})[0] == 403
    assert post(base, {"source": str(ROOT / "demo")}, headers={"Content-Type": "application/json", "Host": "evil.example"})[0] == 403


def test_import_route_errors(base):
    assert post(base, {"source": "/etc"})[0] == 409
    assert post(base, {"source": "ssh://x"})[0] == 409
    assert post(base, {})[0] == 400
    assert post(base, {"source": 5})[0] == 400


def test_test_files_are_not_scanned_as_app_code(tmp_path):
    write(tmp_path, "app.py", 'APP_VERSION = "1.0.0"\ndef f(c):\n    return c.config("x")["real"]\n')
    write(tmp_path, "tests/test_app.py", 'APP_VERSION = "9.9.9"\ndef t(c):\n    return c.config("x")["fixture"]\n')
    write(tmp_path, "test_top.py", 'def t(c):\n    return c.config("y")["z"]\n')
    result = scan_directory(tmp_path)
    assert [f["flag"] for f in result["flags"]] == ["x"]
    assert sorted(reads_of(result, "x")) == ["real"]
    assert [v["version"] for v in result["versions"]] == ["1.0.0"]
    assert any("test file" in n for n in result["notes"])


def test_invalid_semver_is_ignored_not_fatal(tmp_path):
    write(tmp_path, "app.py", 'APP_VERSION = "01.2.3"\ndef f(c):\n    return c.config("x")["a"]\n')
    result = scan_directory(tmp_path)
    assert result["versions"] == [] and result["flags"][0]["flag"] == "x"


def test_parent_path_is_pruned_per_version_only(tmp_path):
    write(tmp_path, "v1/app.py", 'APP_VERSION = "1.0.0"\ndef f(c):\n    return c.config("x")["cta"]\n')
    write(tmp_path, "v3/app.py", 'APP_VERSION = "3.0.0"\ndef f(c):\n    return c.config("x")["cta"]["label"]\n')
    reads = reads_of(scan_directory(tmp_path), "x")
    assert reads["cta"]["required_in"] == ["1.0.0"] and reads["cta.label"]["required_in"] == ["3.0.0"]


def test_calls_in_files_that_never_mention_flagsmith_are_ignored(tmp_path):
    write(tmp_path, "settings.py", 'def f(s):\n    return s.get_value("timeout")["a"]\n', raw=True)
    write(tmp_path, "ui.ts", 'const t = store.getValue("theme");\n')
    assert scan_directory(tmp_path)["flags"] == []


def test_oversized_clone_is_refused(monkeypatch):
    monkeypatch.setattr(importer, "MAX_CLONE_BYTES", 10)
    with pytest.raises(ScanError, match="200 MB"):
        scan_source("https://github.com/owner/big", ok_runner({"big.py": "x" * 100}))
