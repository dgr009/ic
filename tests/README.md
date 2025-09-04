# GCP Services Integration - Comprehensive Test Suite

This directory contains a comprehensive test suite for the GCP services integration, covering unit tests, integration tests, and performance tests.

## Test Structure

```
tests/
├── README.md                          # This file
├── test_requirements.txt              # Testing dependencies
├── test_config.py                     # Test configuration and utilities
├── test_runner.py                     # Main test runner
├── run_tests.py                       # Test execution script
│
├── Unit Tests/
├── test_gcp_utils.py                  # GCP utilities tests
├── test_mcp_gcp_connector.py          # MCP connector tests
├── test_gcp_compute.py                # Compute Engine tests
├── test_gcp_vpc.py                    # VPC Networks tests
├── test_gcp_gke.py                    # Google Kubernetes Engine tests
├── test_gcp_sql.py                    # Cloud SQL tests
├── test_gcp_mock_data.py              # Mock data generators
│
├── integration/                       # Integration tests
├── test_gcp_integration.py            # Real API integration tests
├── integration_config.py              # Integration test configuration
├── cleanup_test_resources.py          # Resource cleanup utility
│
└── performance/                       # Performance tests
    ├── test_gcp_performance.py        # Performance and load tests
    └── benchmark_runner.py            # Benchmarking utility
```

## Test Categories

### 1. Unit Tests

Unit tests validate individual components in isolation using mocks and test data.

**Coverage:**
- ✅ GCP authentication flows (service account, ADC, gcloud)
- ✅ Project discovery and management
- ✅ Resource collection and filtering
- ✅ MCP connector functionality and fallback mechanisms
- ✅ All GCP service modules (Compute, VPC, GKE, SQL, etc.)
- ✅ Output formatting (JSON, YAML, table, tree)
- ✅ Error handling and retry logic

**Key Features:**
- Mock GCP API responses for consistent testing
- Comprehensive error scenario testing
- Authentication method validation
- MCP integration testing with fallback verification

### 2. Integration Tests

Integration tests validate end-to-end functionality with real GCP APIs.

**Coverage:**
- ✅ Real GCP API authentication
- ✅ Project access validation
- ✅ MCP server integration (when available)
- ✅ Service data collection from real APIs
- ✅ Cross-service consistency validation
- ✅ Output formatting with real data
- ✅ Performance characteristics with real APIs

**Configuration:**
- Requires `GCP_INTEGRATION_TEST_PROJECT` environment variable
- Optional: `GCP_INTEGRATION_TEST_REGION`, `GCP_INTEGRATION_TEST_ZONE`
- Enable with `RUN_GCP_INTEGRATION_TESTS=true`

**Safety Features:**
- Automatic resource cleanup
- Test resource labeling
- Dry-run mode for cleanup operations
- Configurable test timeouts

### 3. Performance Tests

Performance tests validate scalability, concurrency, and resource usage.

**Coverage:**
- ✅ Authentication performance
- ✅ Data collection scalability
- ✅ Parallel processing efficiency
- ✅ Memory usage optimization
- ✅ Output formatting performance
- ✅ Rate limiting and retry behavior
- ✅ High concurrency stress testing
- ✅ MCP vs direct API performance comparison

**Metrics:**
- Response times and throughput
- Memory usage patterns
- Concurrency efficiency
- Scalability factors
- Error rates and retry behavior

## Running Tests

### Quick Start

```bash
# Install test dependencies
pip install -r tests/test_requirements.txt

# Run all unit tests
python tests/run_tests.py

# Run specific service tests
python tests/run_tests.py --service compute

# Run with coverage
python tests/run_tests.py --coverage
```

### Unit Tests Only

```bash
# Run all unit tests
python tests/test_runner.py

# Run specific test module
python -m unittest tests.test_gcp_compute -v

# Run specific test class
python -m unittest tests.test_gcp_compute.TestFetchComputeInstancesViaMCP -v
```

### Integration Tests

```bash
# Configure integration tests
export GCP_INTEGRATION_TEST_PROJECT="your-test-project"
export RUN_GCP_INTEGRATION_TESTS="true"

# Run integration tests
python tests/run_tests.py --integration

# Run integration tests for specific project
python tests/integration/test_gcp_integration.py --project your-test-project
```

### Performance Tests

```bash
# Run performance tests
python tests/run_tests.py --performance

# Run comprehensive benchmark
python tests/performance/benchmark_runner.py

# Quick benchmark
python tests/performance/benchmark_runner.py --quick
```

### Resource Cleanup

```bash
# Dry run cleanup (show what would be deleted)
python tests/integration/cleanup_test_resources.py --dry-run

# Force cleanup all test resources
python tests/integration/cleanup_test_resources.py --force

# Cleanup specific service
python tests/integration/cleanup_test_resources.py --service compute
```

## Test Configuration

### Environment Variables

```bash
# Unit Tests
GCP_PROJECTS="project1,project2"
GCP_REGIONS="us-central1,us-east1"
GCP_SERVICE_ACCOUNT_KEY_PATH="/path/to/key.json"

# Integration Tests
GCP_INTEGRATION_TEST_PROJECT="test-project-id"
GCP_INTEGRATION_TEST_REGION="us-central1"
GCP_INTEGRATION_TEST_ZONE="us-central1-a"
RUN_GCP_INTEGRATION_TESTS="true"

# Performance Tests
GCP_API_RESPONSE_THRESHOLD="30.0"
GCP_DATA_COLLECTION_THRESHOLD="60.0"
GCP_PARALLEL_SPEEDUP_MIN="1.2"

# MCP Integration
MCP_GCP_ENABLED="true"
MCP_GCP_ENDPOINT="http://localhost:8080/gcp"
GCP_PREFER_MCP="true"
```

### Configuration Files

- `tests/integration/integration_test_config.json` - Integration test settings
- `tests/test_config.py` - Global test configuration
- `tests/test_requirements.txt` - Python dependencies

## Test Data and Mocks

### Mock Data Generation

The test suite includes comprehensive mock data generators:

```python
from tests.test_gcp_mock_data import GCPMockDataGenerator

generator = GCPMockDataGenerator()

# Generate realistic test data
instance = generator.generate_compute_instance()
network = generator.generate_vpc_network()
cluster = generator.generate_gke_cluster()
```

### Mock API Responses

Mock API responses simulate real GCP API behavior:

```python
from tests.test_gcp_mock_data import GCPMockAPIResponses

# Create mock GCP API objects
mock_instance = GCPMockAPIResponses.create_mock_compute_instance()
mock_cluster = GCPMockAPIResponses.create_mock_gke_cluster()
```

## Continuous Integration

### GitHub Actions Integration

```yaml
name: GCP Services Tests
on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r tests/test_requirements.txt
      - name: Run unit tests
        run: python tests/run_tests.py --coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Authenticate to GCP
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - name: Run integration tests
        env:
          GCP_INTEGRATION_TEST_PROJECT: ${{ secrets.GCP_TEST_PROJECT }}
          RUN_GCP_INTEGRATION_TESTS: "true"
        run: python tests/run_tests.py --integration
```

## Performance Benchmarks

### Baseline Performance Targets

| Metric | Target | Threshold |
|--------|--------|-----------|
| Authentication | < 1s | < 5s |
| Data Collection (1000 items) | < 10s | < 60s |
| Output Formatting (1000 items) | < 2s | < 10s |
| Parallel Speedup (4 cores) | > 2x | > 1.2x |
| Memory Usage (1000 items) | < 50MB | < 100MB |

### Benchmark Reports

Performance benchmarks generate detailed reports:

```bash
# Run benchmark and generate report
python tests/performance/benchmark_runner.py

# Output: gcp_performance_benchmark_YYYYMMDD_HHMMSS.json
```

Report includes:
- System information and test configuration
- Performance metrics and statistics
- Scalability analysis
- Concurrency efficiency
- Memory usage patterns
- Performance recommendations

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure project root is in Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **Authentication Failures**
   ```bash
   # Check GCP credentials
   gcloud auth list
   gcloud auth application-default login
   ```

3. **Integration Test Failures**
   ```bash
   # Verify project access
   gcloud projects describe $GCP_INTEGRATION_TEST_PROJECT
   
   # Check API enablement
   gcloud services list --enabled --project $GCP_INTEGRATION_TEST_PROJECT
   ```

4. **Performance Test Issues**
   ```bash
   # Install performance dependencies
   pip install psutil
   
   # Check system resources
   python -c "import psutil; print(f'CPU: {psutil.cpu_count()}, RAM: {psutil.virtual_memory().total/1024**3:.1f}GB')"
   ```

### Debug Mode

Enable debug logging for detailed test output:

```bash
export PYTHONPATH="$(pwd)"
export GCP_DEBUG="true"
python tests/run_tests.py --verbose
```

## Contributing

### Adding New Tests

1. **Unit Tests**: Add to appropriate `test_gcp_*.py` file
2. **Integration Tests**: Add to `tests/integration/test_gcp_integration.py`
3. **Performance Tests**: Add to `tests/performance/test_gcp_performance.py`

### Test Guidelines

- Use descriptive test names
- Include docstrings explaining test purpose
- Mock external dependencies in unit tests
- Clean up resources in integration tests
- Follow existing patterns and conventions
- Add performance assertions for new features

### Mock Data Guidelines

- Generate realistic test data
- Include edge cases and error conditions
- Maintain consistency with real GCP API responses
- Update mock data when APIs change

## Test Results and Reporting

### Coverage Reports

```bash
# Generate coverage report
python tests/run_tests.py --coverage

# View HTML coverage report
coverage html
open htmlcov/index.html
```

### Test Reports

Test execution generates detailed reports:

- `tests/test_report.json` - Comprehensive test results
- `tests/performance/gcp_performance_benchmark_*.json` - Performance benchmarks
- `tests/integration/cleanup_report_*.json` - Resource cleanup reports

## Security Considerations

### Credential Management

- Never commit real GCP credentials
- Use service accounts with minimal permissions
- Rotate test credentials regularly
- Use separate test projects

### Test Data

- Use synthetic test data only
- Avoid real customer data in tests
- Label all test resources clearly
- Implement automatic cleanup

### Resource Management

- Set resource quotas for test projects
- Monitor test resource usage
- Implement cost alerts
- Clean up resources after tests

## Maintenance

### Regular Tasks

- Update test dependencies monthly
- Review and update mock data quarterly
- Validate integration tests with new GCP API versions
- Update performance baselines as needed
- Clean up old test resources

### Monitoring

- Track test execution times
- Monitor test failure rates
- Review performance trends
- Update thresholds based on infrastructure changes

---

## Summary

This comprehensive test suite provides:

✅ **Complete Coverage**: Unit, integration, and performance tests
✅ **Real-world Validation**: Tests with actual GCP APIs
✅ **Performance Monitoring**: Benchmarks and scalability tests
✅ **Safety Features**: Resource cleanup and error handling
✅ **CI/CD Ready**: Automated testing and reporting
✅ **Developer Friendly**: Easy setup and execution

The test suite ensures the GCP services integration is reliable, performant, and maintainable across all supported services and use cases.