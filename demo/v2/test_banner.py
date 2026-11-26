import os

from flagpact import FlagpactClient

from app import APP_VERSION, render_banner


def test_banner_shows_title_and_button():
    os.environ.setdefault("FLAGPACT_APP_VERSION", APP_VERSION)
    text = render_banner(FlagpactClient.from_env())
    assert text.startswith("[BANNER] ") and text.endswith("]")
