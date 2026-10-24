from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuthToken, User
from apps.results.sync import sync_all_results

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-42"


def make_member(username="회원1", *, is_staff=False, password=PASSWORD):
    return User.objects.create_user(username=username, password=password, is_staff=is_staff)


def signup(username="회원1", password=PASSWORD):
    return APIClient().post("/auth/signup", {"username": username, "password": password}, format="json")


def login(username="회원1", password=PASSWORD):
    return APIClient().post("/auth/login", {"username": username, "password": password}, format="json")


def bearer(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def login_token(username="회원1", password=PASSWORD):
    response = login(username, password)
    assert response.status_code == 200, response.json()
    return response.json()["token"]


# 회원가입


def test_signup_logs_in_and_stores_only_hashes():
    response = signup()
    body = response.json()

    assert response.status_code == 201
    assert body["user"] == {"id": body["user"]["id"], "username": "회원1", "isAdmin": False}
    expires_at = datetime.fromisoformat(body["expiresAt"])
    assert abs(expires_at - (timezone.now() + timedelta(days=7))) < timedelta(minutes=1)
    assert bearer(body["token"]).get("/auth/me").json() == body["user"]

    user = User.objects.get()
    assert user.password != PASSWORD and user.check_password(PASSWORD)
    token = AuthToken.objects.get()
    assert body["token"] not in token.digest and len(token.digest) == 64


def test_signup_rejects_taken_username_ignoring_case():
    assert signup("Member").status_code == 201

    response = signup("member")

    assert response.status_code == 400
    assert response.json() == {"statusCode": 400, "message": "이미 사용 중인 아이디입니다.", "error": "Bad Request"}
    assert User.objects.count() == 1


@pytest.mark.parametrize("password", ["short1", "1234567890", "password", "longusername"])
def test_signup_rejects_weak_password(password):
    response = signup("longusername", password)

    assert response.status_code == 400
    assert response.json()["message"].startswith("password:")
    assert not User.objects.exists()


# "ﬃ"(합자)는 NFKC로 "ffi" 세 글자가 되고, "ﷺ"는 공백이 든 문구가 된다. 저장될 값으로 검사해야 한다.
@pytest.mark.parametrize(
    "username",
    [
        "",
        "has space",
        "bad!",
        "a" * 151,
        pytest.param("ﬃ" * 51, id="nfkc-too-long"),
        pytest.param("ﷺ", id="nfkc-space"),
    ],
)
def test_signup_rejects_invalid_username(username):
    response = signup(username)

    assert response.status_code == 400
    assert response.json()["message"].startswith("username:")
    assert not User.objects.exists()


def test_username_is_normalized_like_stored_value():
    response = signup("ｍｅｍｂｅｒ")

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "member"
    assert login("ｍｅｍｂｅｒ").status_code == 200
    assert signup("member").status_code == 400


def test_password_keeps_surrounding_whitespace():
    assert signup(password=" spaced pass 42 ").status_code == 201

    assert login(password="spaced pass 42").status_code == 400
    assert login(password=" spaced pass 42 ").status_code == 200


# 로그인·로그아웃


def test_login_returns_token_for_member():
    make_member()

    response = login()
    body = response.json()

    assert response.status_code == 200
    assert body["user"]["username"] == "회원1"
    assert bearer(body["token"]).get("/auth/me").status_code == 200


def test_login_failure_does_not_tell_whether_username_exists():
    make_member()
    expected = {"statusCode": 400, "message": "아이디 또는 비밀번호가 올바르지 않습니다.", "error": "Bad Request"}

    assert login(password="wrong-password").json() == expected
    assert login(username="없는회원").json() == expected


def test_inactive_member_cannot_login_and_existing_token_stops_working():
    member = make_member()
    token = login_token()

    member.is_active = False
    member.save()

    assert login().status_code == 400
    assert bearer(token).get("/auth/me").status_code == 401


def test_logout_ends_only_this_device():
    make_member()
    phone, laptop = login_token(), login_token()

    assert bearer(phone).post("/auth/logout").status_code == 204

    assert bearer(phone).get("/auth/me").status_code == 401
    assert bearer(laptop).get("/auth/me").status_code == 200


def test_logout_without_token_is_noop():
    assert APIClient().post("/auth/logout").status_code == 204


@pytest.mark.parametrize("header", [None, "Bearer not-a-token", "Bearer", "Token abc", "Bearer a b"])
def test_me_requires_valid_token(header):
    client = APIClient()
    if header:
        client.credentials(HTTP_AUTHORIZATION=header)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"] == "Unauthorized"


def test_expired_token_is_rejected_and_removed_on_next_login():
    make_member()
    token = login_token()
    AuthToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    assert bearer(token).get("/auth/me").status_code == 401

    login_token()
    assert AuthToken.objects.count() == 1


def test_stale_token_does_not_break_public_api(catalog):
    assert bearer("expired-or-wrong").get("/product").status_code == 200


def test_login_is_throttled():
    make_member()
    for _ in range(10):
        assert login(password="wrong-password").status_code == 400

    response = login()

    assert response.status_code == 429
    assert response.json()["error"] == "Too Many Requests"


def test_login_throttle_ignores_attached_token():
    # 토큰을 붙여도 회원별이 아니라 IP별로 센다.
    make_member()
    token = login_token()
    for _ in range(9):
        login(password="wrong-password")

    response = bearer(token).post("/auth/login", {"username": "회원1", "password": PASSWORD}, format="json")

    assert response.status_code == 429


def test_signup_throttle_ignores_attached_token():
    token = signup("member0").json()["token"]
    for i in range(1, 10):
        assert signup(f"member{i}").status_code == 201

    response = bearer(token).post("/auth/signup", {"username": "member10", "password": PASSWORD}, format="json")

    assert response.status_code == 429


def test_reading_me_is_not_throttled():
    make_member()
    client = bearer(login_token())

    assert all(client.get("/auth/me").status_code == 200 for _ in range(15))


# 비밀번호 변경·탈퇴


def test_change_password_rejects_wrong_current_password():
    make_member()
    client = bearer(login_token())

    response = client.put("/auth/password", {"currentPassword": "wrong", "newPassword": "new-horse-43"}, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "currentPassword: 비밀번호가 올바르지 않습니다."


def test_change_password_rejects_weak_new_password():
    make_member()
    client = bearer(login_token())

    response = client.put("/auth/password", {"currentPassword": PASSWORD, "newPassword": "123"}, format="json")

    assert response.status_code == 400
    assert response.json()["message"].startswith("newPassword:")
    assert User.objects.get().check_password(PASSWORD)


def test_change_password_logs_out_every_device_and_returns_new_token():
    make_member()
    phone, laptop = login_token(), login_token()

    response = bearer(phone).put(
        "/auth/password", {"currentPassword": PASSWORD, "newPassword": "new-horse-43"}, format="json"
    )

    assert response.status_code == 200
    assert bearer(phone).get("/auth/me").status_code == 401
    assert bearer(laptop).get("/auth/me").status_code == 401
    assert bearer(response.json()["token"]).get("/auth/me").status_code == 200
    assert login().status_code == 400
    assert login(password="new-horse-43").status_code == 200


def test_change_password_also_removes_expired_tokens():
    member = make_member()
    client = bearer(login_token())
    AuthToken.objects.create(user=member, digest="0" * 64, expires_at=timezone.now() - timedelta(hours=1))

    response = client.put("/auth/password", {"currentPassword": PASSWORD, "newPassword": "new-horse-43"}, format="json")

    assert response.status_code == 200
    assert AuthToken.objects.count() == 1


def test_change_password_requires_login():
    response = APIClient().put("/auth/password", {"currentPassword": PASSWORD, "newPassword": "x"}, format="json")

    assert response.status_code == 401


def test_withdraw_requires_password():
    make_member()
    client = bearer(login_token())

    response = client.delete("/auth/me", {"password": "wrong"}, format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "password: 비밀번호가 올바르지 않습니다."
    assert User.objects.exists()


def test_withdraw_deletes_member_and_tokens():
    make_member()
    token = login_token()

    assert bearer(token).delete("/auth/me", {"password": PASSWORD}, format="json").status_code == 204

    assert not User.objects.exists()
    assert not AuthToken.objects.exists()
    assert bearer(token).get("/auth/me").status_code == 401
    assert signup().status_code == 201


# 관리자 권한

WRITE_REQUESTS = [
    ("post", "/product", {}),
    ("put", "/product", {}),
    ("delete", "/product", {"ids": [1]}),
    ("post", "/product/all", {"products": []}),
    ("put", "/market", []),
    ("post", "/result", None),
]


@pytest.mark.parametrize(("method", "path", "body"), WRITE_REQUESTS)
def test_write_api_requires_login(method, path, body):
    response = getattr(APIClient(), method)(path, body, format="json")

    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"


@pytest.mark.parametrize(("method", "path", "body"), WRITE_REQUESTS)
def test_write_api_rejects_non_admin_member(method, path, body):
    make_member()

    response = getattr(bearer(login_token()), method)(path, body, format="json")

    assert response.status_code == 403
    assert response.json()["error"] == "Forbidden"


def test_admin_can_write_with_login_token(catalog):
    User.objects.create_superuser("관리자", password=PASSWORD)
    response = login("관리자")
    admin = bearer(response.json()["token"])

    assert response.json()["user"]["isAdmin"] is True
    assert admin.post("/result").status_code == 201
    assert admin.put("/market", [{"name": "새재료", "price": 3}], format="json").status_code == 200


def test_public_api_does_not_need_login(catalog, experiences):
    sync_all_results()
    client = APIClient()

    assert client.get("/product").status_code == 200
    assert client.get("/market").status_code == 200
    assert client.get("/result").status_code == 200
    assert client.get("/experience").status_code == 200
    markets = [{"name": name, "price": 1} for name in ["나무", "못", "천"]]
    assert client.post("/result/calculator", {"markets": markets}, format="json").status_code == 201


def test_old_shared_password_login_is_gone():
    assert APIClient().post("/product/login", {"password": "x"}, format="json").status_code == 404
