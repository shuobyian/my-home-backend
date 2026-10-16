import json

import pytest
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError

from apps.common.exceptions import BadRequest, nest_exception_handler
from apps.common.views import server_error


def test_flatten_paths():
    exc = ValidationError({"a": [{"b": ["m"]}], "c": ["x", "y"], "non_field_errors": ["n"]})

    assert nest_exception_handler(exc, {}).data == {
        "statusCode": 400,
        "message": "a.0.b: m, c: x, c: y, n",
        "error": "Bad Request",
    }
    # detail 키는 경로에 들어가지 않는다
    assert nest_exception_handler(BadRequest("문구"), {}).data["message"] == "문구"


# ValidationError('')는 '', ValidationError()는 '유효하지 않은 입력입니다.'가 나오므로 쓰지 않는다.
@pytest.mark.parametrize("detail", [{}, []])
def test_empty_detail_is_bad_request(detail):
    assert nest_exception_handler(ValidationError(detail), {}).data["message"] == "Bad Request"


def test_server_error_body():
    response = server_error(RequestFactory().get("/"))
    body = json.loads(response.content)

    assert response.status_code == 500
    assert body == {"statusCode": 500, "message": "Internal server error"}
    assert list(body) == ["statusCode", "message"]
