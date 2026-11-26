import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass

SRC = str(pathlib.Path(__file__).resolve().parents[1])


@dataclass
class ReplayResult:
    passed: bool
    output: str


def replay(directory: str, document_path: str, version: str, timeout: float = 60.0) -> ReplayResult:
    env = dict(os.environ)
    env["FLAGPACT_DOCUMENT"] = document_path
    env["FLAGPACT_APP_VERSION"] = version
    env["PYTHONPATH"] = os.pathsep.join([SRC, directory])
    env.pop("FLAGPACT_RECORD_DIR", None)
    try:
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "."],
            cwd=directory, env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ReplayResult(False, "replay timed out")
    return ReplayResult(done.returncode == 0, (done.stdout + done.stderr).strip())
