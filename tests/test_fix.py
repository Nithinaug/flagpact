import json

import pytest

from flagpact.admin import AdminClient
from flagpact.fix import PlanError, apply_plan, move_boundary, plan_fix, publish, rollback
from flagpact.matrix import Cell
from flagpact.verdict import AMBER, GREEN, RED

OLD = {"title": "Sale on now", "heading": "Sale on now", "cta": {"text": "Shop"}}
NEW = {"heading": "Sale on now", "cta": {"text": "Shop"}}


def cells(*states):
    return [Cell(f"{i + 1}.0.0", s, "", {}) for i, s in enumerate(states)]


class FakeFlagsmith:
    def __init__(self):
        self.log = []
        self.segments = []
        self.fsegs = []
        self.states = []
        self.puts = []
        self.default = {"id": 100, "feature_segment": None, "feature_state_value": json.dumps(OLD)}
        self.next_id = 1

    def new_id(self):
        self.next_id += 1
        return self.next_id

    def __call__(self, method, path, body=None, kind="master"):
        self.log.append((method, path.split("?")[0]))
        route = path.split("?")[0]
        if method == "GET" and route.startswith("/environments/") and route.endswith("/featurestates/"):
            return 200, {"results": [self.default]}
        if method == "GET" and route == "/environments/":
            return 200, {"results": [{"id": 7, "api_key": "client"}]}
        if method == "GET" and route.endswith("/features/"):
            return 200, {"results": [{"id": 3, "name": "home_banner"}]}
        if method == "GET" and route.endswith("/segments/"):
            return 200, {"results": self.segments}
        if method == "POST" and route.endswith("/segments/"):
            seg = {"id": self.new_id(), "name": body["name"]}
            self.segments.append(seg)
            return 201, seg
        if method == "GET" and route == "/features/feature-segments/":
            return 200, {"results": self.fsegs}
        if method == "POST" and route == "/features/feature-segments/":
            fseg = {"id": self.new_id(), "segment": body["segment"]}
            self.fsegs.append(fseg)
            return 201, fseg
        if method == "POST" and route == "/features/featurestates/":
            self.states.append(body)
            return 201, body
        if method == "POST" and route.endswith("update-priorities/"):
            return 200, {}
        if method == "PUT" and "/segments/" in route:
            self.puts.append(body)
            return 200, {"id": 1, "name": body["name"]}
        if method == "PATCH" and route.startswith("/environments/"):
            self.default["feature_state_value"] = body["feature_state_value"]
            return 200, {}
        if method == "DELETE":
            return 204, {}
        return 404, {}


def admin(fake):
    return AdminClient(fake, "1", "client")


def test_plan_limit_is_lowest_working_version():
    plan = plan_fix("home_banner", OLD, NEW, cells(RED, RED, GREEN))
    assert plan.limit == "3.0.0"
    assert plan.segment_name == "flagpact/home_banner/3.0.0"
    assert plan.broken == ["1.0.0", "2.0.0"]
    assert len(plan.diff()) == 4


def test_plan_amber_counts_as_working():
    assert plan_fix("f", OLD, NEW, cells(RED, AMBER, GREEN)).limit == "2.0.0"


def test_plan_refuses_non_contiguous_broken_versions():
    with pytest.raises(PlanError, match="manual"):
        plan_fix("f", OLD, NEW, cells(RED, GREEN, RED))


def test_plan_refuses_when_everything_breaks():
    with pytest.raises(PlanError):
        plan_fix("f", OLD, NEW, cells(RED, RED))


def test_plan_refuses_when_nothing_breaks():
    with pytest.raises(PlanError):
        plan_fix("f", OLD, NEW, cells(GREEN, GREEN))


def test_apply_writes_the_rule_but_not_the_default():
    fake = FakeFlagsmith()
    applied = apply_plan(admin(fake), plan_fix("home_banner", OLD, NEW, cells(RED, RED, GREEN)))
    writes = [c for c in fake.log if c[0] in ("POST", "PUT", "PATCH")]
    assert [c[1] for c in writes[:3]] == ["/projects/1/segments/", "/features/feature-segments/", "/features/featurestates/"]
    assert not any(c[0] == "PATCH" and c[1].startswith("/environments/") for c in writes)
    assert json.loads(fake.default["feature_state_value"]) == OLD
    assert json.loads(fake.states[0]["feature_state_value"]["string_value"]) == OLD
    assert applied.created_segment and applied.published is False


def test_publish_changes_the_default_last():
    fake = FakeFlagsmith()
    ad = admin(fake)
    applied = apply_plan(ad, plan_fix("home_banner", OLD, NEW, cells(RED, RED, GREEN)))
    assert publish(ad, applied, NEW) == ["default changed"]
    assert json.loads(fake.default["feature_state_value"]) == NEW
    assert fake.log[-1][0] == "PATCH" and applied.published


def test_rollback_after_publish_restores_default_and_removes_segment():
    fake = FakeFlagsmith()
    ad = admin(fake)
    applied = apply_plan(ad, plan_fix("home_banner", OLD, NEW, cells(RED, RED, GREEN)))
    publish(ad, applied, NEW)
    steps = rollback(ad, applied)
    assert json.loads(fake.default["feature_state_value"]) == OLD
    assert steps == ["default restored", "segment and override removed"]
    assert [c for c in fake.log if c[0] == "DELETE"] == [
        ("DELETE", f"/features/feature-segments/{applied.feature_segment_id}/"),
        ("DELETE", f"/projects/1/segments/{applied.segment_id}/"),
    ]


def test_rollback_before_publish_only_removes_the_rule():
    fake = FakeFlagsmith()
    ad = admin(fake)
    applied = apply_plan(ad, plan_fix("home_banner", OLD, NEW, cells(RED, RED, GREEN)))
    assert rollback(ad, applied) == ["segment and override removed"]
    assert json.loads(fake.default["feature_state_value"]) == OLD


def test_missing_trait_widens_the_rule():
    plan = plan_fix("home_banner", OLD, NEW, cells(RED, RED, GREEN), include_missing=True)
    assert "app_version is not set" in plan.diff()[0]
    body = AdminClient(FakeFlagsmith(), "1", "client").segment_body("n", "3.0.0", True)
    conditions = body["rules"][0]["rules"][0]["conditions"]
    assert [c["operator"] for c in conditions] == ["LESS_THAN", "IS_NOT_SET"]


def test_remote_url_is_refused(monkeypatch):
    monkeypatch.setenv("FLAGSMITH_API_URL", "https://flagsmith.example.com/api/v1")
    from flagpact.admin import AdminError
    with pytest.raises(AdminError):
        AdminClient.from_env()


def test_staged_plan_allows_a_change_that_breaks_nothing():
    plan = plan_fix("home_banner", OLD, NEW, cells(GREEN, GREEN, GREEN), staged=True)
    assert plan.boundaries() == ["3.0.0", "2.0.0", "1.0.0"]
    assert plan.limit == "1.0.0"


def test_staged_plan_leaves_broken_versions_out_of_every_stage():
    plan = plan_fix("home_banner", OLD, NEW, cells(RED, GREEN, GREEN), staged=True)
    assert plan.boundaries() == ["3.0.0", "2.0.0"]
    assert plan.broken == ["1.0.0"]


def test_staged_plan_still_refuses_when_everything_breaks():
    with pytest.raises(PlanError):
        plan_fix("home_banner", OLD, NEW, cells(RED, RED), staged=True)


def test_apply_uses_the_stage_boundary_for_the_rule():
    fake = FakeFlagsmith()
    plan = plan_fix("home_banner", OLD, NEW, cells(GREEN, GREEN, GREEN), staged=True)
    applied = apply_plan(admin(fake), plan, "3.0.0")
    assert applied.boundary == "3.0.0"
    assert plan.segment_name == "flagpact/home_banner/1.0.0"


def test_move_boundary_rewrites_only_the_segment_rule():
    fake = FakeFlagsmith()
    ad = admin(fake)
    plan = plan_fix("home_banner", OLD, NEW, cells(GREEN, GREEN, GREEN), staged=True)
    applied = apply_plan(ad, plan, "3.0.0")
    before = len(fake.log)
    steps = move_boundary(ad, applied, plan, "2.0.0")
    writes = [c for c in fake.log[before:] if c[0] != "GET"]
    assert writes == [("PUT", f"/projects/1/segments/{applied.segment_id}/")]
    condition = fake.puts[0]["rules"][0]["rules"][0]["conditions"][0]
    assert condition["value"] == "2.0.0:semver"
    assert applied.boundary == "2.0.0" and "2.0.0" in steps[0]
