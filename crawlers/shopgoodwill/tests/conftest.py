"""
Pytest configuration for ShopGoodwill tests.
"""

import pytest


def pytest_addoption(parser):
    """Add command-line options for tests."""
    parser.addoption(
        "--run-network-tests", action="store_true", default=False,
        help="Run tests that make real network requests"
    )


@pytest.fixture
def run_network_tests(request):
    """Return whether to run tests that make network requests."""
    return request.config.getoption("--run-network-tests")

