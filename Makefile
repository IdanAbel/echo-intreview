.PHONY: all build deb container test scan clean

# Default: build everything then run tests
all: build test

# Build both the deb package and the final container image
build: deb container

# Step 1: Build the patched nginx .deb from source inside a builder container
deb:
	mkdir -p build/output
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

# Re-scan the patched image and save updated reports
scan:
	mkdir -p reports
	trivy image nginx-patched:latest > reports/patched-trivy.txt
	grype nginx-patched:latest > reports/patched-grype.txt

# Remove build artifacts and stop any leftover containers
clean:
	rm -rf build/output
	docker rm -f orig_nginx patched_nginx builder-inst 2>/dev/null || true
	docker rmi -f nginx-builder nginx-patched:latest 2>/dev/null || true