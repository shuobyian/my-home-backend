import pytest

from apps.common.numbers import format_number, join_numbers, normalize, round_half_up, split_numbers


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (3.0, 3),
        (0.5, 0.5),
        (0.1 + 0.2, 0.3),
        (-0.0, 0),
        (0.9999999999999999, 1),
        (2.0000000000001, 2),
        (12345678.25, 12345678.25),
        # 소수 자릿수가 아니라 유효숫자 기준이라 작은 값도 정밀도를 유지한다
        (0.000012345678, 0.000012345678),
    ],
)
def test_normalize(value, expected):
    result = normalize(value)
    assert result == expected
    assert type(result) is type(expected)


def test_one_third_survives_storage_round_trip():
    stored = split_numbers(join_numbers([1 / 3]))[0]
    assert normalize(stored * 3) == 1


def test_format_number_matches_js_to_string():
    assert format_number(3.0) == "3"
    assert format_number(0.5) == "0.5"
    assert format_number(60.00000000000001) == "60"
    assert format_number(0.000025) == "0.000025"


@pytest.mark.parametrize(("value", "expected"), [(2.5, 3), (86.5, 87), (14.499999999999998, 15), (2.4, 2), (-1.5, -1)])
def test_round_half_up(value, expected):
    assert round_half_up(value) == expected


def test_join_and_split_round_trip():
    assert join_numbers([3.0, 0.5, 12]) == "3,0.5,12"
    assert split_numbers("3,0.5,12") == [3, 0.5, 12]
    assert split_numbers("") == []


def test_split_numbers_tolerates_legacy_garbage():
    assert split_numbers("1,NaN,,abc,inf") == [1, 0, 0, 0, 0]
