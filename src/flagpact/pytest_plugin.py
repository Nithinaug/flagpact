import os

from .contracts import save_contract
from .wrapper import DEFAULT_RECORDER


def pytest_sessionfinish(session, exitstatus):
    root = os.environ.get("FLAGPACT_RECORD_DIR")
    if not root or exitstatus != 0:
        return
    version = os.environ["FLAGPACT_APP_VERSION"]
    sources = [s for s in os.environ.get("FLAGPACT_SOURCES", "").split(os.pathsep) if s]
    recorded_from = sorted({os.path.relpath(item.path) for item in session.items})
    for flag in DEFAULT_RECORDER.flags():
        contract = {
            "flag": flag,
            "app_version": version,
            "recorded_from": ", ".join(recorded_from),
            "reads": DEFAULT_RECORDER.reads_for(flag),
        }
        save_contract(root, contract, sources)
