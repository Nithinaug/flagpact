import json
import pathlib
import subprocess

import pytest

from flagpact.cli import main
from flagpact.importer import ScanError, scan_source

V1 = 'import flagsmith\n\n\ndef banner(c):\n    return c.config("home_banner")["text"]\n'
V2 = 'import flagsmith\n\n\ndef banner(c):\n    value = c.config("home_banner")\n    return value["headline"], value["cta"]["label"], value.get("subtitle", "")\n'


def git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    git(root, "init", "-q")
    (root / "app.py").write_text(V1)
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_it():\n    assert True\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "one")
    git(root, "tag", "v1.0.0")
    (root / "app.py").write_text(V2)
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "two")
    git(root, "tag", "v2.0.0")
    git(root, "tag", "not-a-version")
    return root


def test_each_release_tag_becomes_an_app_version(repo):
    result = scan_source(str(repo))
    assert result["tags"] == ["v1.0.0", "v2.0.0"]
    assert [v["version"] for v in result["versions"]] == ["1.0.0", "2.0.0"]
    assert result["versions"][0]["directory"] == "versions/v1.0.0"
    flag = result["flags"][0]
    assert flag["flag"] == "home_banner"
    reads = {r["path"]: r for r in flag["reads"]}
    assert reads["text"]["required_in"] == ["1.0.0"]
    assert reads["headline"]["required_in"] == ["2.0.0"]
    assert reads["cta.label"]["required_in"] == ["2.0.0"]
    assert reads["subtitle"]["default_in"] == ["2.0.0"] and not reads["subtitle"]["required"]
    assert result["draft"]["versions"] == [
        {"version": "1.0.0", "directory": "versions/v1.0.0"},
        {"version": "2.0.0", "directory": "versions/v2.0.0"},
    ]


def test_a_repo_with_fewer_than_two_tags_uses_the_plain_scan(repo):
    git(repo, "tag", "-d", "v1.0.0")
    result = scan_source(str(repo))
    assert "tags" not in result


def test_checkout_writes_every_file_of_each_tag(repo, tmp_path):
    out = tmp_path / "versions"
    scan_source(str(repo), checkout=str(out))
    assert (out / "v1.0.0" / "app.py").read_text() == V1
    assert (out / "v2.0.0" / "app.py").read_text() == V2
    assert (out / "v1.0.0" / "tests" / "test_app.py").exists()


def test_checkout_refuses_a_folder_that_is_not_empty(repo, tmp_path):
    out = tmp_path / "versions"
    out.mkdir()
    (out / "keep.txt").write_text("x")
    with pytest.raises(ScanError):
        scan_source(str(repo), checkout=str(out))
    assert (out / "keep.txt").read_text() == "x"


def test_checkout_needs_release_tags(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "app.py").write_text(V1)
    with pytest.raises(ScanError):
        scan_source(str(plain), checkout=str(tmp_path / "out"))


def test_cli_prints_the_tags(repo, capsys):
    assert main(["import", str(repo)]) == 0
    assert "Read 2 release tags: v1.0.0, v2.0.0" in capsys.readouterr().out
