import json

import pytest

from conftest import make_document
from flagpact import FlagpactClient, Recorder


class FakeFlags:
    def __init__(self, value):
        self._value = value

    def get_feature_value(self, flag):
        return json.dumps(self._value)


class FakeSDK:
    def __init__(self, value):
        self._value = value
        self.calls = []

    def get_identity_flags(self, identifier, traits=None):
        self.calls.append((identifier, traits))
        return FakeFlags(self._value)


BANNER = {"title": "Sale on now", "heading": "Sale on now", "cta": {"text": "Shop"}}


def client(value=BANNER, version="1.0.0"):
    return FlagpactClient(FakeSDK(value), version)


def test_sends_app_version_trait():
    sdk = FakeSDK(BANNER)
    FlagpactClient(sdk, "2.0.0").config("home_banner")
    assert sdk.calls == [("flagpact-probe", {"app_version": "2.0.0"})]


def test_records_leaf_read_with_type_and_value():
    c = client()
    assert c.config("home_banner")["title"] == "Sale on now"
    assert c.contract("home_banner", "t.py")["reads"] == [
        {"path": "title", "has_default": False, "type": "string", "observed_values": ["Sale on now"]}
    ]


def test_nested_read_records_dotted_path_once():
    c = client()
    cfg = c.config("home_banner")
    assert cfg["cta"]["text"] == "Shop"
    assert cfg.get("cta.text") == "Shop"
    reads = c.contract("home_banner", "t.py")["reads"]
    assert [r["path"] for r in reads] == ["cta.text"]
    assert reads[0]["observed_values"] == ["Shop"]


def test_default_is_recorded_when_value_is_missing():
    c = client()
    assert c.config("home_banner").get("subtitle", "") == ""
    (read,) = c.contract("home_banner", "t.py")["reads"]
    assert read["path"] == "subtitle" and read["has_default"] is True and read["type"] == "missing"


def test_missing_without_default_raises_and_is_required():
    c = client({"heading": "x"})
    with pytest.raises(KeyError):
        c.config("home_banner")["title"]
    (read,) = c.contract("home_banner", "t.py")["reads"]
    assert read["has_default"] is False


def test_reads_merge_across_calls():
    r = Recorder()
    a = FlagpactClient(FakeSDK({"title": "A"}), "1.0.0", r)
    a.config("home_banner")["title"]
    FlagpactClient(FakeSDK({"title": "B"}), "1.0.0", r).config("home_banner")["title"]
    (read,) = r.reads_for("home_banner")
    assert read["observed_values"] == ["A", "B"]


def test_offline_sdk_end_to_end(tmp_path, monkeypatch):
    doc = tmp_path / "env.json"
    doc.write_text(json.dumps(make_document(BANNER)))
    monkeypatch.setenv("FLAGPACT_APP_VERSION", "3.0.0")
    monkeypatch.setenv("FLAGPACT_DOCUMENT", str(doc))
    c = FlagpactClient.from_env()
    assert c.config("home_banner")["cta.text"] == "Shop"
    assert c.contract("home_banner", "t.py")["app_version"] == "3.0.0"
