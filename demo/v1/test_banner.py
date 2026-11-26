import os

from flagpact import FlagpactClient

from app import APP_VERSION, render_banner


def test_banner_shows_non_empty_title():
    os.environ.setdefault("FLAGPACT_APP_VERSION", APP_VERSION)
    text = render_banner(FlagpactClient.from_env())
    title = text.removeprefix("[BANNER] ")
    assert isinstance(title, str) and title.strip()
