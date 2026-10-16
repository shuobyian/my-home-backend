"""API 에러 응답.

프론트엔드 호환을 위해 NestJS의 에러 응답 형식을 그대로 따른다.
    {"statusCode": 400, "message": "...", "error": "Bad Request"}
"""

from http import HTTPStatus

from rest_framework import exceptions
from rest_framework.views import exception_handler


class BadRequest(exceptions.APIException):
    """NestJS의 BadRequestException에 대응한다."""

    status_code = 400
    default_detail = "잘못된 요청입니다."
    default_code = "bad_request"


def nest_error_body(status_code, message):
    body = {"statusCode": status_code, "message": message}
    if status_code < 500:
        body["error"] = HTTPStatus(status_code).phrase
    return body


def nest_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        # 처리되지 않은 예외는 handler500(apps.common.views.server_error)이 응답한다.
        return None
    response.data = nest_error_body(response.status_code, _message(response.data))
    return response


def _message(detail):
    messages = list(_flatten(detail))
    return ", ".join(messages) if messages else HTTPStatus.BAD_REQUEST.phrase


def _flatten(detail, path=()):
    """DRF 에러 상세(dict/list 중첩)를 'field.0.name: 메시지' 형태의 문자열로 편다."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            if key in ("detail", "non_field_errors"):
                yield from _flatten(value, path)
            else:
                yield from _flatten(value, (*path, str(key)))
    elif isinstance(detail, list):
        for index, value in enumerate(detail):
            nested = isinstance(value, (dict, list))
            yield from _flatten(value, (*path, str(index)) if nested else path)
    else:
        yield f"{'.'.join(path)}: {detail}" if path else str(detail)
