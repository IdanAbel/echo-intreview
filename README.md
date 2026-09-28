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
# TODO: paste the baseline version line (README of the first draft says 3.0.11-1~deb12u2)

docker run --rm nginx-patched:latest dpkg -l libssl3 | tail -1
# TODO: paste the patched version line

# TODO: fixed version per the Debian security tracker for CVE-2024-0727 (bookworm): ____
```

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

**Limitation:** the PURL includes `arch=arm64` and the distro qualifier because the image was built on Apple silicon. TODO: state here whether the VEX also matches without qualifiers / on amd64 (I have not verified it).

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

**Known gaps** (not covered yet): a custom configuration file, a large request body, a malformed request line, and a malformed MP4 against `ngx_http_mp4_module`. TODO: remove an item from this list once the test for it exists.

---

## Image size

| Image | Size |
|:------|:-----|
| `nginx:1.25-bookworm` | ~187 MB |
| `nginx-patched:latest` | ~121 MB |

The patched image is about 66 MB smaller. TODO: explain the difference after comparing `nginx -V` and the module list of both images (the official image ships extra dynamic modules, which is a likely cause). Until then, treat "drop-in" as verified for the scenarios in the test table only.

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
| Total matches | TODO | 299 |
| Critical | TODO | 19 |
| High | TODO | 69 |
| Medium | TODO | 88 |

The scanners count differently (for example 306 vs 299 on the same image), so numbers should be compared within one scanner, not across scanners. Most of the reduction comes from the slimmer base image, not from the two CVE fixes.

---

## Residual risk assessment

**What is still there:** about 300 findings remain, almost all in system packages inherited from `debian:bookworm-slim` (for example `libc6`, `coreutils`, `util-linux`) with no upstream fix available (`affected` / `will_not_fix`).

**nginx package:** the scanners flag three CVEs on it: CVE-2023-44487 (false positive, see [VEX](#vex)), and CVE-2009-4487 / CVE-2013-0337 (Negligible / Low, not addressed).

**Scanner blind spot (important):** Trivy and Grype compare my `1.25.5` against Debian's nginx `1.22.1-9+deb12uN` versions. A CVE that Debian has fixed in its 1.22.1 package is therefore treated as fixed for my "newer" 1.25.5, even when upstream 1.25.5 is actually vulnerable. That is exactly why CVE-2024-7347 is invisible to the scanners. The same effect can hide newer nginx CVEs. Debian lists, for example, CVE-2026-42945 and CVE-2026-9256 (both rated Critical, `ngx_http_rewrite_module`) as fixed in its bookworm nginx package. TODO: state here whether nginx 1.25.5 is affected by them (checked against the F5/nginx advisories) or write "not verified". I do not claim that no nginx CVEs with available fixes remain.

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

TODO: list the tools actually used and for what. The first draft of the pipeline was structured with Gemini / Antigravity; the review, verification and README rewrite were done with Claude.

- **Where it helped:** TODO (for example: structuring the Dockerfile pipeline, choosing the OpenVEX format, finding the PURL the scanners use).
- **Where it hurt:** the first README contained an unverified claim about scanner behavior (CVE-2024-7347 "will continue to be flagged"). It was wrong and was corrected only after running the scans and inspecting the JSON output.

## With more time

- Send a malformed MP4 to the patched `ngx_http_mp4_module` and show that the worker survives, to prove the CVE-2024-7347 fix behaviorally and not only by string.
- Add the missing tests: custom config, large body, malformed request line.
- Match the official image's module set exactly and explain the size difference.
- Verify whether nginx 1.25.5 is affected by the 2026 nginx CVEs and, if so, backport the fixes.
- Make the VEX architecture-independent and generate it automatically (for example with `vexctl`) instead of writing it by hand.
- Build for `linux/amd64` as well as `arm64`.