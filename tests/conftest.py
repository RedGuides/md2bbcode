import pytest


def pytest_addoption(parser):
    # Rewrites tests/fixtures/<case>.<dialect>.bbcode from the current output.
    # Run as: hatch test -- --update-goldens
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="rewrite golden fixture outputs instead of comparing against them",
    )


@pytest.fixture
def update_goldens(request):
    return request.config.getoption("--update-goldens")
