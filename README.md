# nginx Drop-in Replacement

A security-hardened drop-in replacement for `nginx:1.25-bookworm`, built from source on a clean `debian:bookworm-slim` base with **2 CVEs eliminated**.

## Quick Start

```bash
# Build the patched .deb and final image
make build

# Run automated compatibility tests
make test

# Re-scan and compare security reports
make scan
```

## How It Works

```
patches/CVE-2024-7347.patch
        │
        ▼
build/Dockerfile  ──►  nginx_1.25.5-1_patched.deb
        │                        │
        │                        ▼
        └──────────►  Containerfile  ──►  nginx-patched:latest
```

1. **`build/Dockerfile`** — downloads nginx 1.25.5 source from nginx.org, applies the backport patch, compiles with the same flags as the official image, and produces a `.deb` package.
2. **`Containerfile`** — starts from `debian:bookworm-slim`, upgrades system libraries (Dependency Bump), installs the patched `.deb`, and recreates the exact environment of `nginx:1.25-bookworm`.

## CVE Fixes

| CVE | Severity | Component | Fix Method | Proof |
|:----|:---------|:----------|:-----------|:------|
| [CVE-2024-7347](https://nvd.nist.gov/vuln/detail/CVE-2024-7347) | Medium | `ngx_http_mp4_module` | Backport patch from upstream commit | `grep -c "unordered mp4" /usr/sbin/nginx` returns `1` on patched, `0` on original |
| [CVE-2024-0727](https://nvd.nist.gov/vuln/detail/CVE-2024-0727) | Medium | `libssl3` (OpenSSL) | Dependency bump via `apt-get --only-upgrade` | Baseline: 743 CVEs → Patched: 306 CVEs |

### CVE-2024-7347 – Backport Patch
**Vulnerability:** Integer overflow and out-of-bounds read in `ngx_http_mp4_module` when processing malformed MP4 files. An attacker can send a crafted MP4 request to crash nginx (DoS) or potentially leak memory.

**Fix:** Backported patch from nginx 1.27.1 onto 1.25.5:
- Changed variable `n` from `uint32_t` to `uint64_t` to prevent integer overflow.
- Added validation that chunk IDs are ordered before processing.

**Binary proof:**
```bash
# Original image (vulnerable) – string NOT found
docker run --rm nginx:1.25-bookworm grep -c "unordered mp4" /usr/sbin/nginx
# → 0

# Patched image (fixed) – string found in binary
docker run --rm nginx-patched:latest grep -c "unordered mp4" /usr/sbin/nginx
# → 1
```

### CVE-2024-0727 – Dependency Bump
**Vulnerability:** Null pointer dereference in OpenSSL when processing a maliciously crafted PKCS12 file. Causes denial of service on any service using `libssl3`.

**Fix:** Upgraded `libssl3` from `3.0.11-1~deb12u2` (vulnerable) to the latest Debian Bookworm security release via:
```dockerfile
apt-get --only-upgrade install -y libssl3 openssl
```

## Image Size Comparison

```bash
docker images | grep -E "nginx"
```

| Image | Size |
|:------|:-----|
| `nginx:1.25-bookworm` | ~187 MB |
| `nginx-patched:latest` | ~121 MB |

## Security Scan Comparison

| Metric | Baseline (`nginx:1.25-bookworm`) | Patched (`nginx-patched:latest`) |
|:-------|:--------------------------------|:---------------------------------|
| Total CVEs | 743 | 306 |
| Critical | 20 | 4 |
| High | 175 | 63 |
| Medium | 293 | 117 |

Full reports: [`reports/baseline-trivy.txt`](reports/baseline-trivy.txt) vs [`reports/patched-trivy.txt`](reports/patched-trivy.txt)

## Compatibility Tests

```bash
make test
```

The test suite (`test/test_compat.py`) starts both `nginx:1.25-bookworm` and `nginx-patched:latest` side-by-side and validates:

| Test | What it checks |
|:-----|:--------------|
| GET / | Status 200, identical body, correct Server header |
| GET /not-found | Status 404 on both images |
| HEAD / | Same status and Content-Type |
| POST / | Same status code for POST to static path |
| PATCH / | Same handling of unsupported HTTP methods |
| Log symlinks | `access.log` → `/dev/stdout` on both images |
| CVE-2024-7347 patch | Binary proof: `0` matches in original, `1` in patched |

## Residual Risk Assessment

After patching, **306 CVEs remain** in the image. These are all in system packages inherited from `debian:bookworm-slim` (e.g., `libc6`, `coreutils`, `util-linux`) that have no available upstream fix at this time (status: `affected` or `will_not_fix`).

**Mitigations considered:**
- The nginx binary itself has been patched and compiled from source – no nginx-specific CVEs remain that have available fixes.
- A move to a `distroless` or `scratch`-based image would eliminate most of the remaining OS-level CVEs.
- Regular re-scanning via `make scan` is recommended to catch newly published CVEs.

## Notes

- AI tooling (Gemini / Antigravity) was used to help structure the Dockerfile pipeline and patch validation strategy.
- The backport patch was sourced from the official nginx changelog and security advisory for 1.27.1/1.26.2.
- Scanner limitation: Trivy and Grype will continue to flag CVE-2024-7347 because they match by package version string (`1.25.5`), not by binary inspection. The binary proof above serves as the definitive evidence of remediation.