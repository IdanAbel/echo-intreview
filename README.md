# nginx Drop-in Replacement

A drop-in replacement for `nginx:1.25-bookworm`, **rebuilt from source** on a clean `debian:bookworm-slim` base, with two CVEs fixed using two different techniques:

| Technique | CVE | Component |
|:----------|:----|:----------|
| **Backport** of an upstream patch | CVE-2024-7347 | nginx `ngx_http_mp4_module` |
| **Version bump** of a dependency | CVE-2024-0727 | `libssl3` (OpenSSL) |

The repo also contains an automated compatibility test against the original image, before/after scans with **both Trivy and Grype**, and an OpenVEX document.

**Read this first (honest summary):**

- The two fixes are real and verifiable (see [CVE fixes](#cve-fixes)).
- Trivy and Grype **do not flag CVE-2024-7347** on this build (details in [What surprised me](#what-surprised-me)), so that fix cannot be shown "disappearing" from a scan. Its proof is a binary check, not a scanner diff.
- The VEX demo (CVE disappearing from both scanners) is done on **CVE-2023-44487**, which is *not* one of my patches: nginx >= 1.25.3 already contains the mitigation and the scanners flag it from Debian version data. The VEX is only an attestation of that.

---

## Prerequisites

`docker`, `trivy`, `grype`, `jq`, `make`, `python3`.

## Quick start

```bash
make build   # build the patched .deb (build/Dockerfile) and the final image (Containerfile)
make test    # run the compatibility test: nginx:1.25-bookworm vs nginx-patched:latest
make scan    # scan the patched image with Trivy and Grype and write reports/
make vex     # re-scan with the VEX file applied (Trivy + Grype), write reports/*-vex.txt
```

## How it works

```
patches/CVE-2024-7347.patch
        |
        v
build/Dockerfile  -->  nginx_1.25.5-1~custom.patched.deb
        |                        |
        |                        v
        +---------->  Containerfile  -->  nginx-patched:latest
```

1. **`build/Dockerfile`** starts from `debian:bookworm-slim`, downloads the nginx 1.25.5 source from nginx.org, applies the backport patch, compiles with the same flags as the official image, and packages the result as a `.deb`. No prebuilt nginx binaries and no `apt install nginx`.
2. **`Containerfile`** starts from `debian:bookworm-slim`, bumps system libraries (`libssl3`), installs the patched `.deb`, and recreates the environment of `nginx:1.25-bookworm` (`docker-entrypoint.sh`, log symlinks, exposed port, stop signal, default command).

## Repository layout

| Path | Purpose |
|:-----|:--------|
| `build/` | Dockerfile that builds the patched `.deb` from upstream source |
| `patches/CVE-2024-7347.patch` | The backported patch, named after the CVE it fixes |
| `Containerfile` | Produces the final image from the `.deb` |
| `docker-entrypoint.sh` | Entrypoint, mirrored from the official image |
| `test/` | Compatibility test (`test_compat.py`) |
| `vex/CVE-2024-7347.openvex.json` | OpenVEX attestation |
| `reports/` | Baseline and patched scan outputs (Trivy and Grype), with and without VEX |
| `Makefile` | One-command entry points (`build`, `test`, `scan`, `vex`) |

---

## CVE fixes

| CVE | Severity | Fix method | Evidence |
|:----|:---------|:-----------|:---------|
| [CVE-2024-7347](https://nvd.nist.gov/vuln/detail/CVE-2024-7347) | Medium | **Backport** (nginx 1.27.1 -> 1.25.5) | [`patches/CVE-2024-7347.patch`](patches/CVE-2024-7347.patch); binary check below; [upstream commit](https://github.com/nginx/nginx/commit/88955b1044ef38315b77ad1a509d63631a790a0f) |
| [CVE-2024-0727](https://nvd.nist.gov/vuln/detail/CVE-2024-0727) | Medium | **Version bump** (`libssl3`) | `dpkg -l libssl3` before/after below |
| [CVE-2023-44487](https://nvd.nist.gov/vuln/detail/CVE-2023-44487) | High (Grype) / Low (Trivy) | **Not fixed by me.** VEX (`not_affected`) | Mitigation already in nginx >= 1.25.3; [`vex/CVE-2024-7347.openvex.json`](vex/CVE-2024-7347.openvex.json); [`reports/patched-trivy-vex.txt`](reports/patched-trivy-vex.txt) |

Removal of components was not used for any of the required CVEs.

### CVE-2024-7347: backport

**Vulnerability:** integer overflow and out-of-bounds read in `ngx_http_mp4_module` when processing crafted MP4 files (crash / possible memory disclosure). Present in nginx 1.25.5, fixed upstream in 1.27.1.

**Fix:** the upstream fix backported onto 1.25.5:

- `n` changed from `uint32_t` to `uint64_t` to prevent the overflow;
- added validation that chunk IDs are ordered before processing (this adds the error string `unordered mp4 chunks`).

**Evidence.** The new error string exists only in a binary that contains the patch:

```bash
# Original image: string NOT present
docker run --rm nginx:1.25-bookworm grep -c "unordered mp4" /usr/sbin/nginx
# -> 0

# Patched image: string present
docker run --rm nginx-patched:latest grep -c "unordered mp4" /usr/sbin/nginx
# -> 1
```

**What this proves and what it does not.** It proves the patch is compiled into the shipped binary. It does not prove the exploit is blocked: I did not send a malformed MP4 to the patched module (see [With more time](#with-more-time)).

### CVE-2024-0727: dependency bump

**Vulnerability:** NULL pointer dereference in OpenSSL when processing a crafted PKCS12 file (denial of service for anything using `libssl3`).

**Fix:** `libssl3` upgraded to the latest Debian bookworm security release:

```bash
apt-get --only-upgrade install -y libssl3 openssl
```

**Evidence:**

```bash
docker run --rm nginx:1.25-bookworm dpkg -l libssl3 | tail -1
# ii  libssl3:arm64  3.0.11-1~deb12u2  arm64  Secure Sockets Layer toolkit - shared libraries

docker run --rm nginx-patched:latest dpkg -l libssl3 | tail -1
# ii  libssl3:arm64  3.0.22-1~deb12u1  arm64  Secure Sockets Layer toolkit - shared libraries

# Debian bookworm fixed version for CVE-2024-0727: 3.0.13-1~deb12u1
```

The Debian security tracker lists `3.0.13-1~deb12u1` as the bookworm fixed version. The patched image is newer than that fixed version. [Debian security tracker](https://security-tracker.debian.org/tracker/CVE-2024-0727)

Note: the total CVE count dropping from 743 to 306 is *not* evidence for this CVE. It reflects the smaller base image and the other upgraded libraries, so I do not use it as proof.

---

## Triage

All CVEs in the baseline reports were reviewed at the level of "which package is flagged and is a code fix available". The ones I picked, and why:

| CVE | Component | Upstream fix | Chosen method | Why |
|:----|:----------|:-------------|:--------------|:----|
| CVE-2024-7347 | nginx mp4 module | nginx 1.27.1 | Backport | Small, self-contained patch; 1.25.5 predates the fix; the result is verifiable in the binary |
| CVE-2024-0727 | libssl3 | Debian bookworm security update | Version bump | The fix already ships in Debian, so a bump is the right tool and no source work is needed |
| CVE-2023-44487 | nginx HTTP/2 | Mitigations released in nginx 1.25.3 | None (VEX only) | Already included in 1.25.5; scanners flag it from Debian version data ([nginx advisory](https://www.f5.com/company/blog/nginx/http-2-rapid-reset-attack-impacting-f5-nginx-products)) |
| CVE-2009-4487, CVE-2013-0337 | nginx | Not evaluated | Not addressed | Negligible/Low severity, old, and I did not find a code fix to backport (not researched in depth) |

The scanners flag exactly three CVEs on the `nginx` package (the three above). None of them is a real, unfixed code issue with a backportable patch, which is why the backport target is a CVE the scanners do not flag (see below).

---

## VEX

`vex/CVE-2024-7347.openvex.json` is an [OpenVEX](https://openvex.dev) document with two statements, both `not_affected`:

| CVE | Justification | Effect on scanners |
|:----|:--------------|:-------------------|
| CVE-2023-44487 | `inline_mitigations_already_exist` (nginx >= 1.25.3, this build is 1.25.5) | **Removed** from both scanners' reports |
| CVE-2024-7347 | `vulnerable_code_not_present` (backport applied) | None, since the scanners never flag it on this build. It documents the fix. |

The product identifier is the exact PURL both scanners report for the patched image:
`pkg:deb/debian/nginx@1.25.5-1~custom.patched?arch=arm64&distro=debian-12.15`.

**Result for CVE-2023-44487 on `nginx-patched:latest`** (same image, only the `--vex` flag differs):

| Scanner | Without VEX | With VEX |
|:--------|:------------|:---------|
| Trivy | 1 match | 0 |
| Grype | 1 match | 0 |

```bash
make vex   # writes reports/patched-trivy-vex.txt and reports/patched-grype-vex.txt
```

The VEX changes only what the scanners *report*. It changes no code, and it is only as trustworthy as the statement inside it.

**Limitation:** the PURL includes `arch=arm64` and `distro=debian-12.15`, matching the image used to generate these reports. The VEX file was verified on arm64 only; an amd64 build must generate or validate its own matching PURL before this attestation is reused.

---

## Compatibility tests

```bash
make test
```

`test/test_compat.py` boots `nginx:1.25-bookworm` and `nginx-patched:latest` as separate containers, sends the same requests to both, and compares the results.

**What "working correctly" means:** for every scenario, the patched image returns the same status code, the same relevant headers and the same body as the original. Any mismatch fails the run with a non-zero exit code.

| Test | What it checks |
|:-----|:---------------|
| `GET /` | Status 200, identical body, correct `Server` header |
| `GET /not-found` | 404 on both images |
| `HEAD /` | Same status and `Content-Type` |
| `POST /` | Same status for a POST to a static path |
| `PATCH /` | Same handling of an unsupported method |
| Log symlinks | `access.log` -> `/dev/stdout` on both images |
| CVE-2024-7347 patch | Binary check: `0` matches in original, `1` in patched |
| Custom config | The same mounted nginx config returns identical status, `Content-Type`, and body |
| Large request body | A 2 MiB POST is rejected identically by both images |
| Malformed HTTP request | A raw invalid request line returns the same status, `Content-Type`, and body |

**Known gap:** the suite does not yet send a malformed MP4 to `ngx_http_mp4_module`; therefore it verifies that the backport is compiled into the binary, but not the exploit behavior itself.

---

## Image size

| Image | Size |
|:------|:-----|
| `nginx:1.25-bookworm` | 193 MB |
| `nginx-patched:latest` | 123 MB |

The patched image is about 70 MB smaller. The upstream scan detects 144 OS packages while the patched scan detects 108. The replacement intentionally uses `debian:bookworm-slim`, installs only nginx runtime dependencies and does not include the upstream image's additional operating-system packages. Drop-in behavior is verified for the scenarios in the test table, not as a byte-for-byte image equivalent.

---

## Scan comparison

Baseline = `nginx:1.25-bookworm`, patched = `nginx-patched:latest`.

**Trivy** (`reports/baseline-trivy.txt` vs `reports/patched-trivy.txt`):

| Metric | Baseline | Patched |
|:-------|:---------|:--------|
| Total CVEs | 743 | 306 |
| Critical | 20 | 4 |
| High | 175 | 63 |
| Medium | 293 | 117 |

**Grype** (`reports/baseline-grype.txt` vs `reports/patched-grype.txt`):

| Metric | Baseline | Patched |
|:-------|:---------|:--------|
| Total matches | 720 | 299 |
| Critical | 47 | 19 |
| High | 244 | 69 |
| Medium | 249 | 88 |

The scanners count differently (for example 306 vs 299 on the same image), so numbers should be compared within one scanner, not across scanners. Most of the reduction comes from the slimmer base image, not from the two CVE fixes.

---

## Residual risk assessment

**What is still there:** 306 Trivy findings and 299 Grype matches remain. They are predominantly in OS packages (for example `libc6`, `coreutils`, and `util-linux`); the scanner reports include a mixture of `affected`, `will_not_fix`, and unknown fix status.

**nginx package:** the scanners flag three CVEs on it: CVE-2023-44487 (false positive, see [VEX](#vex)), and CVE-2009-4487 / CVE-2013-0337 (Negligible / Low, not addressed).

**Scanner blind spot (important):** Trivy and Grype compare my `1.25.5` package against Debian nginx package versions. A CVE that Debian has fixed in its `1.22.1-9+deb12uN` package can therefore be treated as fixed for this newer-looking `1.25.5` version even if upstream `1.25.5` is vulnerable. That is exactly why CVE-2024-7347 is invisible to the scanners. I do not claim that no nginx CVEs with available fixes remain; upstream nginx advisories must be tracked separately.

**What I would do next:**

1. Track nginx advisories directly (F5/nginx.org) and diff them against my version, instead of relying only on scanner output.
2. Move the runtime to a distroless base to remove most OS-level findings.
3. Re-scan regularly (`make scan`) and keep the VEX document reviewed, since a VEX statement can go stale.

---

## What surprised me

1. **The scanners do not flag CVE-2024-7347 at all**, on the original image or on mine. Debian fixes it in 1.22.1-9+deb12u2, scanners compare version strings, and 1.25.5 sorts higher, so it looks fixed even though upstream 1.25.5 was vulnerable. An earlier draft of this README claimed the opposite without having been checked. I only found out by running the scan and querying the JSON output. Consequence: the binary check is the only proof of this fix, and the VEX demo uses CVE-2023-44487.
2. **Trivy and Grype disagree**: Trivy reports no nginx findings for the official image but three for mine, and they rate CVE-2023-44487 differently (Low vs High). I did not investigate why.
3. **The VEX does not fix anything.** It made CVE-2023-44487 disappear from the reports while the image bytes were unchanged. Fixing (a code change, verified in the binary) and suppressing (an attestation) are different things, and the README keeps them separate.

## AI usage

Gemini / Antigravity helped structure the first pipeline. Claude was used for review, verification and the first README rewrite. Codex was used to compare the image against upstream, add compatibility coverage, rebuild the image, and re-run the tests and scans.

- **Where it helped:** scaffolding the Docker build pipeline, identifying the OpenVEX format, extracting scanner PURLs, and proposing test cases.
- **Where it hurt:** an early README asserted scanner behavior for CVE-2024-7347 without a scan result. That claim was wrong and was removed after inspecting the reports. All security assertions in this README are now tied to a command, binary check, or saved report.

## With more time

- Send a malformed MP4 to the patched `ngx_http_mp4_module` and show that the worker survives, to prove the CVE-2024-7347 fix behaviorally and not only by string.
- Verify upstream nginx advisories that are not visible to Debian-version-based scanners and backport applicable fixes.
- Make the VEX architecture-independent and generate it automatically (for example with `vexctl`) instead of writing it by hand.
- Build for `linux/amd64` as well as `arm64`.
