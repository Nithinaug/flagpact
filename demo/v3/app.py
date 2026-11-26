from flagpact import FlagpactClient

APP_VERSION = "3.0.0"


def render_banner(client: FlagpactClient) -> str:
    cfg = client.config("home_banner")
    subheading = cfg.get("subheading", "")
    return f"[BANNER] {cfg['heading']} | {subheading} [{cfg['cta']['label']}]"
