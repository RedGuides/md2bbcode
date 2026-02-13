from typing import Optional
from urllib.parse import parse_qs, quote, urlencode, urlparse

_RASTER_SHIELDS_BASE = "https://raster.shields.io"
_WESERV_BASE = "https://images.weserv.nl/"


def rewrite_svg_url(url: str) -> Optional[str]:
    if not url:
        return url

    parsed = urlparse(url)
    if _is_github_actions_badge(parsed):
        return _rewrite_github_actions_badge(parsed)

    if _should_rasterize(parsed):
        if parsed.scheme not in ("http", "https"):
            return None
        return _wrap_weserv(url)

    return url


def _is_github_actions_badge(parsed) -> bool:
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc.lower() != "github.com":
        return False

    parts = parsed.path.strip("/").split("/")
    return (
        len(parts) >= 6
        and parts[2] == "actions"
        and parts[3] == "workflows"
        and parts[5].lower() == "badge.svg"
    )


def _rewrite_github_actions_badge(parsed) -> str:
    parts = parsed.path.strip("/").split("/")
    owner = parts[0]
    repo = parts[1]
    workflow = parts[4]

    query = parse_qs(parsed.query)
    params = {}
    if query.get("branch"):
        params["branch"] = query["branch"][0]
    if query.get("event"):
        params["event"] = query["event"][0]

    base = f"{_RASTER_SHIELDS_BASE}/github/actions/workflow/status/{owner}/{repo}/{workflow}.png"
    if params:
        base = f"{base}?{urlencode(params)}"
    return base


def _should_rasterize(parsed) -> bool:
    path = parsed.path.lower()
    if path.endswith(".svg"):
        return True
    return False


def _wrap_weserv(url: str) -> str:
    encoded = quote(url, safe="")
    return f"{_WESERV_BASE}?url={encoded}&output=png"
