.PHONY: all build deb container test baseline scan vex clean

VEX_FILE := vex/CVE-2024-7347.openvex.json

# Default: build everything then run tests
all: build test

# Build both the deb package and the final container image
build: deb container

# Step 1: Build the patched nginx .deb from source inside a builder container
deb:
	mkdir -p build/output
	docker rm -f builder-inst 2>/dev/null || true
	docker build -t nginx-builder -f build/Dockerfile .
	docker create --name builder-inst nginx-builder
	docker cp builder-inst:/output/nginx_1.25.5-1_patched.deb build/output/
	docker rm -f builder-inst

# Step 2: Build the final drop-in replacement image from the .deb
container:
	docker build -t nginx-patched:latest -f Containerfile .

# Run the automated HTTP compatibility test suite
test:
	python3 test/test_compat.py

# Scan the ORIGINAL image with Trivy and Grype (baseline).
# Note: scanner databases change daily, so re-running overwrites the old baseline numbers.
baseline:
	mkdir -p reports
	docker pull nginx:1.25-bookworm
	trivy image nginx:1.25-bookworm > reports/baseline-trivy.txt
	grype nginx:1.25-bookworm > reports/baseline-grype.txt

# Re-scan the patched image and save updated reports
scan:
	mkdir -p reports
	trivy image nginx-patched:latest > reports/patched-trivy.txt
	grype nginx-patched:latest > reports/patched-grype.txt

# Re-scan the patched image with the OpenVEX document applied (Trivy + Grype)
vex:
	@test -f $(VEX_FILE) || (echo "Missing $(VEX_FILE)"; exit 1)
	mkdir -p reports
	trivy image --vex $(VEX_FILE) --show-suppressed nginx-patched:latest > reports/patched-trivy-vex.txt
	grype nginx-patched:latest --vex $(VEX_FILE) > reports/patched-grype-vex.txt

# Remove build artifacts and stop any leftover containers
clean:
	rm -rf build/output
	docker rm -f orig_nginx patched_nginx orig_nginx_conf patched_nginx_conf builder-inst 2>/dev/null || true
	docker rmi -f nginx-builder nginx-patched:latest 2>/dev/null || true