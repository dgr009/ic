# Platform Test Runner Makefile

.PHONY: help test test-all test-unit test-integration test-performance
.PHONY: test-ncp test-ncpgov test-aws test-gcp test-oci test-azure
.PHONY: discover clean install-deps

# Default target
help:
	@echo "Platform Test Runner Commands:"
	@echo ""
	@echo "Test Execution:"
	@echo "  make test-all          - Run all tests"
	@echo "  make test-unit         - Run all unit tests"
	@echo "  make test-integration  - Run all integration tests"
	@echo "  make test-performance  - Run all performance tests"
	@echo ""
	@echo "Platform-specific tests:"
	@echo "  make test-ncp          - Run NCP platform tests"
	@echo "  make test-ncpgov       - Run NCP Gov platform tests"
	@echo "  make test-aws          - Run AWS platform tests"
	@echo "  make test-gcp          - Run GCP platform tests"
	@echo "  make test-oci          - Run OCI platform tests"
	@echo "  make test-azure        - Run Azure platform tests"
	@echo ""
	@echo "Service-specific tests (example):"
	@echo "  make test-ncp-ec2      - Run NCP EC2 service tests"
	@echo "  make test-ncp-s3       - Run NCP S3 service tests"
	@echo ""
	@echo "Utilities:"
	@echo "  make discover          - Discover available tests"
	@echo "  make clean             - Clean test artifacts"
	@echo "  make install-deps      - Install test dependencies"

# Install test dependencies
install-deps:
	pip install pytest pytest-json-report rich pyyaml psutil

# Test discovery
discover:
	python platform_test_runner.py --discover-only

# Run all tests
test-all:
	python run_platform_tests.py all

# Run tests by type
test-unit:
	python run_platform_tests.py unit

test-integration:
	python run_platform_tests.py integration

test-performance:
	python run_platform_tests.py performance

# Run tests by platform
test-ncp:
	python run_platform_tests.py platform ncp

test-ncpgov:
	python run_platform_tests.py platform ncpgov

test-aws:
	python run_platform_tests.py platform aws

test-gcp:
	python run_platform_tests.py platform gcp

test-oci:
	python run_platform_tests.py platform oci

test-azure:
	python run_platform_tests.py platform azure

# Run tests by service (NCP examples)
test-ncp-ec2:
	python run_platform_tests.py service ncp ec2

test-ncp-s3:
	python run_platform_tests.py service ncp s3

test-ncp-vpc:
	python run_platform_tests.py service ncp vpc

test-ncp-sg:
	python run_platform_tests.py service ncp sg

test-ncp-rds:
	python run_platform_tests.py service ncp rds

# Run tests by service (NCPGOV examples)
test-ncpgov-ec2:
	python run_platform_tests.py service ncpgov ec2

test-ncpgov-s3:
	python run_platform_tests.py service ncpgov s3

test-ncpgov-vpc:
	python run_platform_tests.py service ncpgov vpc

test-ncpgov-sg:
	python run_platform_tests.py service ncpgov sg

test-ncpgov-rds:
	python run_platform_tests.py service ncpgov rds

# Advanced test execution with options
test-fail-fast:
	python platform_test_runner.py --fail-fast

test-with-output:
	python platform_test_runner.py --output test_results.json

test-ncp-only:
	python platform_test_runner.py --platforms ncp --output ncp_results.json

test-unit-only:
	python platform_test_runner.py --test-types unit --output unit_results.json

# Clean test artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -f /tmp/pytest_report.json
	rm -f test_results*.json

# Continuous Integration targets
ci-unit:
	python platform_test_runner.py --test-types unit --fail-fast --output ci_unit_results.json

ci-integration:
	python platform_test_runner.py --test-types integration --fail-fast --output ci_integration_results.json

ci-all:
	python platform_test_runner.py --fail-fast --output ci_all_results.json