"""Static routes and the Host check: the single-page-app fallback serves only files inside app/web/dist, and the
app answers only to the loopback host names it is served on (127.0.0.1, localhost).

The only file outside the build folder that is ever requested is a harmless canary that this test writes just
outside app/web/dist and deletes afterwards. Precondition: web app built (app/web/dist), Exasol running.
"""

from __future__ import annotations

import http.client
import uuid
from urllib.parse import quote, urlsplit

import pytest

from tests.support.appserver import REPO_ROOT, app_server

pytestmark = pytest.mark.exasol
DIST = REPO_ROOT / "app" / "web" / "dist"


@pytest.fixture(scope="module")
def canary():
    path = DIST.parent / f"vp-canary-{uuid.uuid4().hex[:12]}.txt"  # app/web/, one level above the build folder
    token = f"canary {uuid.uuid4().hex}"
    path.write_text(token, encoding="utf-8")
    try:
        yield path, token
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture(scope="module")
def base(canary):
    if not (DIST / "index.html").exists():
        pytest.skip("web app not built (npm run build in app/web)")
    with app_server() as url:
        yield url


def raw_get(base: str, path: str, host: str | None = None) -> tuple[int, str]:
    """GET with the request path sent exactly as written: no client-side clean-up of `..` or %-escapes."""
    u = urlsplit(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=60)
    try:
        conn.request("GET", path, headers={"Host": host or u.netloc})
        r = conn.getresponse()
        return r.status, r.read().decode("utf-8", "replace")
    finally:
        conn.close()


def traversal_paths(canary_path) -> list[str]:
    name = canary_path.name
    absolute = canary_path.resolve()
    return [
        f"/../{name}",                      # raw
        f"/..%2F{name}",                    # encoded slash
        f"/..%2f{name}",
        f"/%2e%2e/{name}",                  # encoded dots
        f"/%2E%2E/{name}",
        f"/..%5C{name}",                    # encoded backslash
        f"/%2e%2e%2f{name}",                # fully encoded
        f"/%2e%2e%5c{name}",
        f"/location/..%2F..%2F..%2F{name}",  # deeper, under a page route
        f"/assets/..%2F..%2F{name}",        # under the static assets mount
        f"/assets/../../{name}",
        "/" + quote(absolute.as_posix(), safe="/:"),  # absolute path (with drive letter on Windows)
        "/" + quote(str(absolute), safe=""),        # absolute path, native separators, fully encoded
    ]


def test_traversal_never_returns_a_file_outside_the_build_folder(base, canary):
    path, token = canary
    assert path.read_text(encoding="utf-8") == token  # the canary is in place while we probe
    leaks = {}
    for p in traversal_paths(path):
        status, body = raw_get(base, p)
        if token in body or status == 200:
            leaks[p] = status
    assert not leaks, f"traversal variants answered 200 or returned the canary: {leaks}"


def test_pages_and_assets_still_load(base):
    status, home = raw_get(base, "/")
    assert status == 200 and '<div id="root">' in home
    for page in ["/index.html", "/location/183/2018-07", "/location/183/day/2018-07-17", "/event/183-201807171842",
                 "/methodology", "/sources", "/no-such-page"]:
        status, body = raw_get(base, page)
        assert (status, body) == (200, home), page  # the app shell; the router shows the page
    assets = sorted((DIST / "assets").iterdir())
    assert assets
    for f in assets:
        status, body = raw_get(base, f"/assets/{f.name}")
        assert status == 200 and body == f.read_bytes().decode("utf-8", "replace"), f.name
    status, _ = raw_get(base, "/api/no-such-route")
    assert status == 404


def test_only_loopback_host_names_are_answered(base):
    port = urlsplit(base).port
    for host in [f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"]:
        assert raw_get(base, "/", host=host)[0] == 200, host
    for host in [f"attacker.example:{port}", "attacker.example", f"127.0.0.1.attacker.example:{port}",
                 f"localhost.attacker.example:{port}", f"192.168.1.10:{port}"]:
        for path in ["/", "/api/meta", "/assets/does-not-matter.js"]:
            assert raw_get(base, path, host=host)[0] == 400, (host, path)
