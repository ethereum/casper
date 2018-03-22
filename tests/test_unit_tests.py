import pytest


@pytest.mark.parametrize(
    'dynasty',
    [
        (0),
        (1),
        (99999),
        (-100),
        (-1),
    ]
)
def test_dynasty_wei_delta_defaults(casper, dynasty):
    assert casper.get_dynasty_wei_delta(dynasty) == 0
