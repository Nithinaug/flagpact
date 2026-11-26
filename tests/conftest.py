import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


def make_document(value: dict, flag: str = "home_banner") -> dict:
    return {
        "id": 1,
        "api_key": "offline-test",
        "name": "flagpact-test",
        "updated_at": "2026-11-26T00:00:00+00:00",
        "project": {
            "id": 1,
            "name": "flagpact-test",
            "hide_disabled_flags": False,
            "organisation": {
                "id": 1, "name": "flagpact-test", "feature_analytics": False,
                "persist_trait_data": True, "stop_serving_flags": False,
            },
            "segments": [],
        },
        "segment_overrides": [],
        "feature_states": [{
            "django_id": 1,
            "featurestate_uuid": "00000000-0000-0000-0000-000000000001",
            "enabled": True,
            "feature_state_value": json.dumps(value),
            "multivariate_feature_state_values": [],
            "feature": {"id": 1, "name": flag, "type": "STANDARD"},
        }],
    }
