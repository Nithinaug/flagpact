import copy
import json
import pathlib

from flagpact.risks import detect, notices, partial
from flagpact.service import Service

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCUMENT = json.loads((ROOT / "demo" / "environment.json").read_text())
FEATURE = {"id": 1, "name": "home_banner", "type": "STANDARD"}
NEW = {"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}


def with_split():
    doc = copy.deepcopy(DOCUMENT)
    doc["project"]["segments"].append({
        "id": 50,
        "name": "half",
        "rules": [{"type": "ALL", "rules": [{"type": "ANY", "rules": [], "conditions": [
            {"operator": "PERCENTAGE_SPLIT", "value": "50", "property_": None}]}], "conditions": []}],
        "feature_states": [{"feature": dict(FEATURE), "enabled": True, "django_id": 5, "feature_segment": {"priority": 0},
                            "featurestate_uuid": "u", "feature_state_value": "{}", "multivariate_feature_state_values": []}],
    })
    return doc


class Stub:
    def __init__(self, doc):
        self.doc = doc

    def document(self):
        return self.doc


def test_a_clean_document_has_no_risks():
    assert detect(DOCUMENT, "home_banner") == {"multivariate": False, "percentage": [], "identity_overrides": 0}
    assert notices(DOCUMENT, "home_banner") == [] and partial(DOCUMENT, "home_banner") is False


def test_a_percentage_split_on_this_flag_is_found():
    found = detect(with_split(), "home_banner")
    assert found["percentage"] == ["half"]
    assert any("percentage rollout" in line for line in notices(with_split(), "home_banner"))


def test_a_split_on_another_flag_is_ignored():
    doc = with_split()
    doc["project"]["segments"][-1]["feature_states"][0]["feature"]["name"] = "other"
    assert detect(doc, "home_banner")["percentage"] == []


def test_multivariate_values_are_found():
    doc = copy.deepcopy(DOCUMENT)
    doc["feature_states"][0]["multivariate_feature_state_values"] = [{"id": 1, "percentage_allocation": 50}]
    assert detect(doc, "home_banner")["multivariate"] is True and partial(doc, "home_banner")


def test_identity_overrides_warn_but_do_not_make_results_partial():
    doc = copy.deepcopy(DOCUMENT)
    doc["identity_overrides"] = [{"identifier": "vip", "identity_features": [{"feature": dict(FEATURE)}]}]
    assert detect(doc, "home_banner")["identity_overrides"] == 1
    assert any("1 identities" in line for line in notices(doc, "home_banner"))
    assert partial(doc, "home_banner") is False


def test_a_split_stops_the_matrix_from_saying_safe():
    service = Service(Stub(with_split()), str(ROOT / "flagpact.json"))
    result = service.check(NEW, replay=True)
    states = [c["state"] for c in result["cells"]]
    assert "green" not in states
    assert any("partly checked" in c["reason"] for c in result["cells"])


def test_the_state_carries_the_notices():
    service = Service(Stub(with_split()), str(ROOT / "flagpact.json"))
    assert service.state()["notices"]
