import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.logs.models import Action, ActivityLog

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-42"


def make_member(username="회원1", *, is_staff=False):
    return User.objects.create_user(username=username, password=PASSWORD, nickname="늘흰", is_staff=is_staff)


def login(username="회원1", password=PASSWORD):
    client = APIClient(HTTP_USER_AGENT="pytest-browser")
    return client.post("/auth/login", {"username": username, "password": password}, format="json")


def admin_client():
    client = APIClient()
    client.force_authenticate(user=make_member("관리자", is_staff=True))
    return client


def actions():
    return list(ActivityLog.objects.order_by("id").values_list("action", "username"))


def test_account_activity_is_logged():
    signup = APIClient().post(
        "/auth/signup", {"username": "회원1", "password": PASSWORD, "nickname": "늘흰"}, format="json"
    )
    assert signup.status_code == 201
    login("회원1", "wrong-password")
    token = login().json()["token"]
    member = APIClient()
    member.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    member.patch("/auth/me", {"nickname": "새벽"}, format="json")
    token = member.put(
        "/auth/password", {"currentPassword": PASSWORD, "newPassword": "battery-staple-77"}, format="json"
    ).json()["token"]
    member.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    member.post("/auth/logout")

    assert actions() == [
        (Action.SIGNUP, "회원1"),
        (Action.LOGIN_FAILED, "회원1"),
        (Action.LOGIN, "회원1"),
        (Action.PROFILE_UPDATE, "회원1"),
        (Action.PASSWORD_CHANGE, "회원1"),
        (Action.LOGOUT, "회원1"),
    ]
    failed = ActivityLog.objects.get(action=Action.LOGIN_FAILED)
    assert (failed.user, failed.ip, failed.user_agent) == (None, "127.0.0.1", "pytest-browser")
    assert ActivityLog.objects.get(action=Action.PROFILE_UPDATE).detail == {"before": "늘흰", "after": "새벽"}
    # 비밀번호는 어디에도 남기지 않는다.
    assert not ActivityLog.objects.filter(detail__icontains="battery").exists()


def test_failed_login_with_odd_body_is_logged_without_username():
    response = APIClient().post("/auth/login", [], format="json")

    assert response.status_code == 400
    assert actions() == [(Action.LOGIN_FAILED, "")]


def test_logout_without_token_logs_nothing():
    assert APIClient().post("/auth/logout").status_code == 204
    assert actions() == []


def test_withdrawal_log_keeps_username():
    member = make_member()
    client = APIClient()
    client.force_authenticate(user=member)

    assert client.delete("/auth/me", {"password": PASSWORD}, format="json").status_code == 204

    log = ActivityLog.objects.get(action=Action.WITHDRAW)
    assert (log.user, log.username) == (None, "회원1")


def test_only_admin_reads_logs():
    make_member()
    member = APIClient()
    member.force_authenticate(user=User.objects.get(username="회원1"))

    assert APIClient().get("/log").status_code == 401
    assert member.get("/log").status_code == 403


def test_admin_filters_logs():
    make_member()
    login()
    login("회원1", "wrong-password")
    login("없는회원", "wrong-password")
    ActivityLog.objects.create(action=Action.REPORT_CREATE, username="회원1", report_id=7)
    admin = admin_client()

    body = admin.get("/log", {"page": 0, "size": 2}).json()
    assert body["totalElements"] == 4
    assert [(log["action"], log["username"]) for log in body["content"]] == [
        ("REPORT_CREATE", "회원1"),
        ("LOGIN_FAILED", "없는회원"),
    ]
    assert body["content"][0].keys() == {
        "id",
        "action",
        "userId",
        "username",
        "reportId",
        "detail",
        "ip",
        "userAgent",
        "createdAt",
    }
    assert admin.get("/log", {"action": "LOGIN_FAILED"}).json()["totalElements"] == 2
    assert admin.get("/log", {"username": "없는"}).json()["totalElements"] == 1
    assert admin.get("/log", {"reportId": 7}).json()["totalElements"] == 1
    assert admin.get("/log", {"action": "HACK"}).status_code == 400
