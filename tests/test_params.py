import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.common.exceptions import BadRequest
from apps.common.params import query_int


def make_request(params=None):
    return Request(APIRequestFactory().get("/", params or {}))


@pytest.mark.parametrize(
    ("raw", "kwargs", "message"),
    [
        ("abc", {}, "count 값은 숫자여야 합니다."),
        ("inf", {}, "count 값은 숫자여야 합니다."),
        ("nan", {}, "count 값은 숫자여야 합니다."),
        ("1.5", {}, "count 값은 정수여야 합니다."),
        ("1000001", {"max_value": 1_000_000}, "count 값은 1000000 이하여야 합니다."),
        # params에 그대로 넣으면 %00으로 인코딩됐다가 되돌아온다
        ("\x00", {}, "count 값이 올바르지 않습니다."),
        (None, {"required": True}, "count 값이 필요합니다."),
    ],
)
def test_query_int_messages(raw, kwargs, message):
    request = make_request(None if raw is None else {"count": raw})

    with pytest.raises(BadRequest) as error:
        query_int(request, "count", **kwargs)

    assert error.value.detail == message


# 현재 동작 고정(characterization). 의도한 스펙이 아니며, 바꾸려면 API 계약 변경으로 따로 다룬다.
@pytest.mark.parametrize(
    ("raw", "kwargs", "expected"),
    [
        ("2.0", {}, 2),
        ("1e1", {}, 10),
        (" 2 ", {}, 2),
        # 범위 검사가 정수 검사보다 먼저 일어난다
        ("0.5", {"min_value": 1}, "count 값은 1 이상이어야 합니다."),
    ],
)
def test_query_int_float_parsing_characterization(raw, kwargs, expected):
    request = make_request({"count": raw})

    if isinstance(expected, str):
        with pytest.raises(BadRequest) as error:
            query_int(request, "count", **kwargs)
        assert error.value.detail == expected
    else:
        assert query_int(request, "count", **kwargs) == expected


def test_empty_query_value_is_missing():
    assert query_int(make_request({"count": ""}), "count", default=7) == 7
