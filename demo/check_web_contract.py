"""Verify every API call in web/src matches a real server route (method + path).

Usage: python3 demo/check_web_contract.py
Exit non-zero on any mismatch.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/home/user/TUS/server")
from app.main import app  # noqa: E402

ROOT = Path("/home/user/TUS")


def norm(path: str) -> str:
    path = re.sub(r"\$\{[^}]+\}", "{p}", path)   # ${var} -> {p}
    path = re.sub(r"\{[^}]+\}", "{p}", path)       # {param} -> {p}
    return path


server_routes: set[tuple[str, str]] = set()
for r in app.routes:
    route_path = getattr(r, "path", "")
    if not route_path.startswith("/api/v1/"):
        continue
    for m in getattr(r, "methods", set()) or set():
        server_routes.add((m, norm(route_path[len("/api/v1"):])))
print(f"server routes: {len(server_routes)}")

CALL = re.compile(r"(?:api|axios)\.(get|post|put|patch|delete)\(\s*[`'\"]([^`'\"]+)[`'\"]")
HELPER_GET = re.compile(r"(?<![a-zA-Z_.])get<[^>]+>\(\s*[`'\"]([^`\'\"]+)[`\'\"]")
web_calls: set[tuple[str, str]] = set()
for f in (ROOT / "web/src").rglob("*"):
    if f.suffix not in (".ts", ".tsx"):
        continue
    text = f.read_text()
    for m in CALL.finditer(text):
        method, raw = m.group(1).upper(), m.group(2)
        raw = raw.replace("${BASE}", "")
        if not raw.startswith("/"):
            continue
        web_calls.add((method, norm(raw)))
    for m in HELPER_GET.finditer(text):
        raw = m.group(1)
        if raw.startswith("/"):
            web_calls.add(("GET", norm(raw)))
print(f"web api calls: {len(web_calls)}")

missing = sorted(web_calls - server_routes)
if missing:
    print("\nMISMATCH — web calls with NO server route:")
    for m, p in missing:
        print(f"  {m} {p}")
    sys.exit(1)

unused = sorted(server_routes - {(m, p) for m, p in web_calls})
print("\nserver routes not (yet) called by web UI:")
for m, p in unused:
    print(f"  {m} {p}")
print("\nCONTRACT CHECK PASSED — every web API call matches a server route")
