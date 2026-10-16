import io

from django.core.exceptions import RequestDataTooBig
from rest_framework import exceptions
from rest_framework.parsers import JSONParser


class RequestEntityTooLarge(exceptions.APIException):
    status_code = 413
    default_detail = "request entity too large"
    default_code = "request_entity_too_large"


class LimitedJSONParser(JSONParser):
    """DATA_UPLOAD_MAX_MEMORY_SIZE(50MB)를 JSON 본문에도 적용한다.

    DRF JSONParser는 요청 스트림을 바로 읽어서 Django의 본문 크기 제한을 거치지 않는다.
    request.body를 읽으면 Django가 Content-Length를 먼저 확인하고 너무 크면 읽지 않고 거절한다.
    """

    def parse(self, stream, media_type=None, parser_context=None):
        request = parser_context["request"]._request
        try:
            body = request.body
        except RequestDataTooBig:
            raise RequestEntityTooLarge() from None
        return super().parse(io.BytesIO(body), media_type, parser_context)
