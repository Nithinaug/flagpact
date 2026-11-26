import os

from flagpact import FlagpactClient

from app import APP_VERSION, render_banner


def test_banner_shows_title_with_optional_subtitle():
    os.environ.setdefault("FLAGPACT_APP_VERSION", APP_VERSION)
    text = render_banner(FlagpactClient.from_env())
    assert text.startswith("[BANNER] ") and len(text) > len("[BANNER] ")
