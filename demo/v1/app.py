from flagpact import FlagpactClient

APP_VERSION = "1.0.0"


def render_banner(client: FlagpactClient) -> str:
    cfg = client.config("home_banner")
    heading = cfg.get("heading", "")
    return f"[BANNER] {cfg['title']}" + (f" | {heading}" if heading else "")
