#!/usr/bin/env python3
"""
Compatibility test suite for nginx-patched:latest
Proves drop-in replacement behavior vs nginx:1.25-bookworm
"""

import subprocess
import time
import sys
import socket
import shlex
from pathlib import Path
import urllib.request
import urllib.error

ORIGINAL_IMAGE = "nginx:1.25-bookworm"
PATCHED_IMAGE  = "nginx-patched:latest"
PORT_ORIGINAL  = 8081
PORT_PATCHED   = 8082
PORT_ORIGINAL_CONFIG = 8083
PORT_PATCHED_CONFIG  = 8084
CUSTOM_CONFIG = Path(__file__).parent / "fixtures" / "custom-default.conf"

PASS = 0
FAIL = 0

def run(cmd):
    subprocess.run(cmd, shell=True, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_for(port, path="/", timeout=15):
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def request(port, path="/", method="GET", data=None, headers=None):
    url = f"http://localhost:{port}{path}"
    req = urllib.request.Request(url, data=data,
                                  headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()

def check(name, orig, patched):
    global PASS, FAIL
    if orig == patched:
        print(f"  ✅  PASS  {name}")
        PASS += 1
    else:
        print(f"  ❌  FAIL  {name}")
        print(f"       original: {orig}")
        print(f"       patched:  {patched}")
        FAIL += 1

def raw_request(port, payload):
    """Send an intentionally malformed request and return status, headers, body."""
    with socket.create_connection(("localhost", port), timeout=5) as conn:
        conn.sendall(payload)
        chunks = []
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

    head, body = b"".join(chunks).split(b"\r\n\r\n", 1)
    lines = head.decode("iso-8859-1").split("\r\n")
    headers = {}
    for line in lines[1:]:
        key, value = line.split(":", 1)
        headers[key.lower()] = value.strip()
    return lines[0], headers, body

def main():
    print("\n══════════════════════════════════════════")
    print("   nginx drop-in replacement test suite")
    print("══════════════════════════════════════════\n")

    # Start both containers in detached mode
    print("▶ Starting containers...")
    run("docker rm -f orig_nginx patched_nginx 2>/dev/null || true")
    run(f"docker run -d --name orig_nginx    -p {PORT_ORIGINAL}:80 {ORIGINAL_IMAGE}")
    run(f"docker run -d --name patched_nginx -p {PORT_PATCHED}:80  {PATCHED_IMAGE}")

    # Wait until both are ready to serve requests
    assert wait_for(PORT_ORIGINAL), "❌ Original nginx failed to start"
    assert wait_for(PORT_PATCHED),  "❌ Patched  nginx failed to start"
    print("✅ Both containers healthy\n")

    # ────── TEST 1: GET / ──────
    # Verify root page returns 200, identical body, and correct Server header
    print("── Test 1: GET / (root page) ──")
    s1o, h1o, b1o = request(PORT_ORIGINAL, "/")
    s1p, h1p, b1p = request(PORT_PATCHED,  "/")
    check("status code",    s1o, s1p)
    check("body content",   b1o, b1p)
    check("Server header contains 'nginx'",
          "nginx" in h1o.get("Server","").lower(),
          "nginx" in h1p.get("Server","").lower())

    # ────── TEST 2: 404 ──────
    # Verify that missing pages return 404 on both images
    print("\n── Test 2: GET /not-found (404) ──")
    s2o, _, _ = request(PORT_ORIGINAL, "/this-page-does-not-exist")
    s2p, _, _ = request(PORT_PATCHED,  "/this-page-does-not-exist")
    check("404 status code", s2o, s2p)

    # ────── TEST 3: HEAD ──────
    # Verify HEAD method returns same status and Content-Type
    print("\n── Test 3: HEAD / ──")
    s3o, h3o, _ = request(PORT_ORIGINAL, "/", method="HEAD")
    s3p, h3p, _ = request(PORT_PATCHED,  "/", method="HEAD")
    check("HEAD status code",          s3o, s3p)
    check("HEAD Content-Type matches", h3o.get("Content-Type"),
                                       h3p.get("Content-Type"))

    # ────── TEST 4: POST / ──────
    # Verify POST to a static path returns same status on both images       
    print("\n── Test 4: POST / (small body) ──")
    s4o, _, _ = request(PORT_ORIGINAL, "/", method="POST", data=b"hello=world")
    s4p, _, _ = request(PORT_PATCHED,  "/", method="POST", data=b"hello=world")
    check("POST status code", s4o, s4p)

    # ────── TEST 5: Unknown method ──────
    # Verify unsupported HTTP methods are handled identically
    print("\n── Test 5: Unknown HTTP method ──")
    s5o, _, _ = request(PORT_ORIGINAL, "/", method="PATCH")
    s5p, _, _ = request(PORT_PATCHED,  "/", method="PATCH")
    check("PATCH status code", s5o, s5p)

    # ────── TEST 6: Log symlinks ──────
    # Verify access.log is a symlink to /dev/stdout (required for docker logs)
    print("\n── Test 6: Log symlinks (stdout/stderr) ──")
    lo = subprocess.run(
        "docker exec orig_nginx ls -la /var/log/nginx/access.log",
        shell=True, capture_output=True, text=True).stdout
    lp = subprocess.run(
        "docker exec patched_nginx ls -la /var/log/nginx/access.log",
        shell=True, capture_output=True, text=True).stdout
    check("access.log -> /dev/stdout",
          "/dev/stdout" in lo, "/dev/stdout" in lp)

    # ────── TEST 7: CVE-2024-7347 backport patch verification ──────
    # The patch added a unique string to the binary that does NOT exist in the original.
    # original: 0 matches (vulnerable), patched: 1 match (fixed)
    print("\n── Test 7: CVE-2024-7347 patch embedded in binary ──")
    count_orig = subprocess.run(
        "docker exec orig_nginx grep -c 'unordered mp4' /usr/sbin/nginx || true",
        shell=True, capture_output=True, text=True).stdout.strip()
    count_patch = subprocess.run(
        "docker exec patched_nginx grep -c 'unordered mp4' /usr/sbin/nginx || true",
        shell=True, capture_output=True, text=True).stdout.strip()

    print(f"       original binary match count : {count_orig}  (expected: 0 – vulnerable)")
    print(f"       patched  binary match count : {count_patch}  (expected: 1 – fixed)")
    check("patch NOT in original (CVE present)",  count_orig,  "0")
    check("patch IN patched image (CVE fixed)",   count_patch, "1")

    # ────── TEST 8: Custom configuration ──────
    # Mount the same replacement default.conf into both images. This verifies
    # that a caller can supply nginx configuration without image-specific work.
    print("\n── Test 8: custom configuration ──")
    config_path = shlex.quote(str(CUSTOM_CONFIG.resolve()))
    mount = f"-v {config_path}:/etc/nginx/conf.d/default.conf:ro"
    run("docker rm -f orig_nginx_conf patched_nginx_conf 2>/dev/null || true")
    run(f"docker run -d --name orig_nginx_conf -p {PORT_ORIGINAL_CONFIG}:80 "
        f"{mount} {ORIGINAL_IMAGE}")
    run(f"docker run -d --name patched_nginx_conf -p {PORT_PATCHED_CONFIG}:80 "
        f"{mount} {PATCHED_IMAGE}")
    assert wait_for(PORT_ORIGINAL_CONFIG, "/custom"), "❌ Original custom config failed"
    assert wait_for(PORT_PATCHED_CONFIG, "/custom"), "❌ Patched custom config failed"
    s8o, h8o, b8o = request(PORT_ORIGINAL_CONFIG, "/custom")
    s8p, h8p, b8p = request(PORT_PATCHED_CONFIG, "/custom")
    check("custom-config status", s8o, s8p)
    check("custom-config Content-Type", h8o.get("Content-Type"), h8p.get("Content-Type"))
    check("custom-config body", b8o, b8p)
    run("docker rm -f orig_nginx_conf patched_nginx_conf")

    # ────── TEST 9: Large request body ──────
    # 2 MiB exceeds nginx's default 1 MiB limit. Both images must reject it
    # in the same way rather than hanging or producing different responses.
    print("\n── Test 9: POST / (large body) ──")
    large_body = b"x" * (2 * 1024 * 1024)
    s9o, h9o, b9o = request(PORT_ORIGINAL, "/", method="POST", data=large_body)
    s9p, h9p, b9p = request(PORT_PATCHED,  "/", method="POST", data=large_body)
    check("large-body status", s9o, s9p)
    check("large-body Content-Type", h9o.get("Content-Type"), h9p.get("Content-Type"))
    check("large-body body", b9o, b9p)

    # ────── TEST 10: Malformed request ──────
    # Use a raw socket because urllib cannot construct an invalid request line.
    print("\n── Test 10: malformed HTTP request ──")
    malformed = b"NOT-HTTP\r\nHost: localhost\r\nConnection: close\r\n\r\n"
    s10o, h10o, b10o = raw_request(PORT_ORIGINAL, malformed)
    s10p, h10p, b10p = raw_request(PORT_PATCHED, malformed)
    check("malformed-request status", s10o, s10p)
    check("malformed-request Content-Type", h10o.get("content-type"), h10p.get("content-type"))
    check("malformed-request body", b10o, b10p)

    print("\n══════════════════════════════════════════")
    print(f"   Results:  {PASS} passed  |  {FAIL} failed")
    print("══════════════════════════════════════════\n")

    run("docker rm -f orig_nginx patched_nginx orig_nginx_conf patched_nginx_conf")

    if FAIL > 0:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 Fatal error: {e}", file=sys.stderr)
        run("docker rm -f orig_nginx patched_nginx orig_nginx_conf patched_nginx_conf 2>/dev/null || true")
        sys.exit(1)
