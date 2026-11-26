from flagpact import FlagpactClient

APP_VERSION = "2.0.0"


def render_banner(client: FlagpactClient) -> str:
    cfg = client.config("home_banner")
    subtitle = cfg.get("subtitle", "")
    return f"[BANNER] {cfg['title']} {subtitle}".strip()
