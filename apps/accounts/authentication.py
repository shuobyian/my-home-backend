from rest_framework.authentication import BaseAuthentication, get_authorization_header

from apps.accounts.tokens import find_token


class BearerTokenAuthentication(BaseAuthentication):
    """Authorization: Bearer <토큰> 헤더로 로그인한 회원을 찾는다.

    토큰이 없거나 틀리거나 만료됐으면 익명으로 처리한다. 오래된 토큰이 붙어 와도 공개 API는 그대로 응답하고,
    로그인이 필요한 API는 권한 검사에서 401(WWW-Authenticate: Bearer)이 된다.
    """

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b"bearer":
            return None
        token = find_token(parts[1])
        if token is None:
            return None
        return token.user, token

    def authenticate_header(self, request):
        return "Bearer"
