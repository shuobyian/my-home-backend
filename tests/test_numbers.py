import pytest

from apps.common.numbers import format_number, join_numbers, normalize, split_numbers


@pytest.mark.parametrize(
    ("value", "expected"),
    [(3.0, 3), (0.5, 0.5), (0.1 + 0.2, 0.3), (-0.0, 0), (2.0000000001, 2), (12345678.25, 12345678.25)],
)
def test_normalize(value, expected):
    result = normalize(value)
    assert result == expected
    assert type(result) is type(expected)


def test_format_number_matches_js_to_string():
    assert format_number(3.0) == "3"
    assert format_number(0.5) == "0.5"
    assert format_number(60.00000000000001) == "60"


def test_join_and_split_round_trip():
    assert join_numbers([3.0, 0.5, 12]) == "3,0.5,12"
    assert split_numbers("3,0.5,12") == [3, 0.5, 12]
    assert split_numbers("") == []
