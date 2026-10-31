import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.experiences.models import Experience
from apps.logs.models import Action, ActivityLog
from apps.markets.models import Market
from apps.products.models import Material
from apps.reports.models import Report

pytestmark = pytest.mark.django_db


def member_client(username="회원1", *, is_staff=False):
    user = User.objects.create_user(username=username, password="correct-horse-42", nickname="늘흰", is_staff=is_staff)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def level_90(value=10000000):
    # experiences fixture의 90레벨 경험치는 190,000이다.
    return {"target": "EXPERIENCE", "targetId": Experience.objects.get(level=90).pk, "field": "amount", "value": value}


def report_body(*changes, **fields):
    return {"kind": "DATA", "title": "90레벨 경험치가 틀려요", "content": "", "changes": list(changes), **fields}


def write_report(client, *changes, **fields):
    response = client.post("/report", report_body(*changes, **fields), format="json")
    assert response.status_code == 201, response.json()
    return response.json()


def test_writing_requires_login(experiences):
    response = APIClient().post("/report", report_body(level_90()), format="json")

    assert response.status_code == 401
    assert not Report.objects.exists()


def test_member_reports_what_value_should_be(experiences):
    body = write_report(member_client(), level_90())

    assert body["status"] == "OPEN"
    assert body["author"]["nickname"] == "늘흰"
    assert body["changes"] == [
        {
            "target": "EXPERIENCE",
            "targetId": Experience.objects.get(level=90).pk,
            "label": "90레벨",
            "field": "amount",
            "before": 190000,
            "after": 10000000,
        }
    ]
    log = ActivityLog.objects.get(action=Action.REPORT_CREATE)
    assert (log.username, log.report_id, log.detail) == ("회원1", body["id"], {"title": "90레벨 경험치가 틀려요"})


def test_change_can_point_at_market_product_and_material(catalog):
    plank = catalog["판자"]
    body = write_report(
        member_client(),
        {"target": "MARKET", "targetId": Market.objects.get(name="나무").pk, "field": "price", "value": 12},
        {"target": "PRODUCT", "targetId": plank.pk, "field": "tool", "value": "FIRE_PIT"},
        {"target": "MATERIAL", "targetId": Material.objects.get(product=plank).pk, "field": "count", "value": 2.5},
    )

    assert [(c["label"], c["field"], c["before"], c["after"]) for c in body["changes"]] == [
        ("나무", "price", 10, 12),
        ("판자", "tool", "WOOD", "FIRE_PIT"),
        ("판자 · 나무", "count", 3, 2.5),
    ]


def test_bug_report_needs_no_change():
    body = write_report(
        member_client(), kind="BUG", title="저장 버튼이 안 눌려요", content="물품 관리에서 저장이 안 됩니다."
    )

    assert (body["kind"], body["changes"]) == ("BUG", [])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"field": "level"}, "바꿀 수 없는 값입니다. (amount)"),
        ({"value": 190000}, "현재 값과 같습니다."),
        ({"value": -1}, "changes.0.value: 이 값이 0보다 크거나 같은지 확인하세요."),
        ({"value": "많이"}, "value"),
        ({"targetId": 999999}, "존재하지 않는 대상입니다."),
        ({"target": "SHOP"}, "target"),
    ],
)
def test_invalid_change_is_rejected(experiences, change, message):
    response = member_client().post("/report", report_body({**level_90(), **change}), format="json")

    assert response.status_code == 400
    assert message in response.json()["message"]
    assert not Report.objects.exists()


def test_report_needs_content_or_change():
    response = member_client().post("/report", report_body(), format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "내용이나 바꿀 값을 입력해주세요."


def test_same_value_twice_is_rejected(experiences):
    response = member_client().post("/report", report_body(level_90(), level_90(20000000)), format="json")

    assert response.status_code == 400
    assert response.json()["message"] == "같은 값을 두 번 넣었습니다. (90레벨 amount)"


def test_reading_requires_login(experiences):
    created = write_report(member_client(), level_90())
    anon = APIClient()

    assert anon.get("/report").status_code == 401
    assert anon.get(f"/report/{created['id']}").status_code == 401


def test_member_reads_own_reports_with_filters(experiences):
    member = member_client()
    data = write_report(member, level_90())
    bug = write_report(member, kind="BUG", title="버그", content="화면이 깨져요")

    listed = member.get("/report", {"page": 0, "size": 10}).json()
    assert listed["totalElements"] == 2
    assert [report["id"] for report in listed["content"]] == [bug["id"], data["id"]]
    assert [r["id"] for r in member.get("/report", {"kind": "DATA"}).json()["content"]] == [data["id"]]
    assert member.get("/report", {"status": "RESOLVED"}).json()["totalElements"] == 0
    assert member.get(f"/report/{data['id']}").json() == data
    assert member.get("/report/999999").status_code == 404
    assert member.get("/report", {"status": "DONE"}).status_code == 400


def test_member_does_not_see_others_reports(experiences):
    mine = write_report(member_client(), level_90())
    other = member_client("회원2")
    theirs = write_report(other, kind="BUG", title="버그", content="화면이 깨져요")

    listed = other.get("/report").json()
    assert (listed["totalElements"], [r["id"] for r in listed["content"]]) == (1, [theirs["id"]])
    assert other.get(f"/report/{mine['id']}").status_code == 404


def test_admin_sees_every_report(experiences):
    mine = write_report(member_client(), level_90())
    theirs = write_report(member_client("회원2"), kind="BUG", title="버그", content="화면이 깨져요")
    admin = member_client("관리자", is_staff=True)

    listed = admin.get("/report").json()
    assert [r["id"] for r in listed["content"]] == [theirs["id"], mine["id"]]
    assert admin.get(f"/report/{mine['id']}").json() == mine


def test_author_edits_open_report_and_changes_are_replaced(experiences):
    member = member_client()
    created = write_report(member, level_90())

    response = member.put(
        f"/report/{created['id']}",
        report_body(level_90(9000000), title="90레벨은 900만"),
        format="json",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["title"] == "90레벨은 900만"
    assert [change["after"] for change in response.json()["changes"]] == [9000000]
    assert ActivityLog.objects.filter(action=Action.REPORT_UPDATE, report_id=created["id"]).exists()


def test_only_author_edits_or_deletes(experiences):
    created = write_report(member_client(), level_90())
    other = member_client("회원2")

    assert other.put(f"/report/{created['id']}", report_body(level_90()), format="json").status_code == 403
    assert other.delete(f"/report/{created['id']}").status_code == 403
    assert Report.objects.filter(pk=created["id"]).exists()


def test_admin_answers_and_author_can_no_longer_edit(experiences):
    member = member_client()
    created = write_report(member, level_90())
    admin = member_client("관리자", is_staff=True)

    assert member.patch(f"/report/{created['id']}", {"status": "RESOLVED"}, format="json").status_code == 403
    response = admin.patch(f"/report/{created['id']}", {"status": "RESOLVED", "answer": "반영했습니다."}, format="json")

    assert response.status_code == 200, response.json()
    assert (response.json()["status"], response.json()["answer"]) == ("RESOLVED", "반영했습니다.")
    log = ActivityLog.objects.get(action=Action.REPORT_ANSWER)
    assert (log.username, log.detail["status"]) == ("관리자", "RESOLVED")
    assert member.put(f"/report/{created['id']}", report_body(level_90()), format="json").status_code == 403
    assert member.delete(f"/report/{created['id']}").status_code == 403


def test_author_deletes_open_report_and_log_remains(experiences):
    member = member_client()
    created = write_report(member, level_90())

    assert member.delete(f"/report/{created['id']}").status_code == 204

    assert not Report.objects.exists()
    log = ActivityLog.objects.get(action=Action.REPORT_DELETE)
    assert (log.report_id, log.detail) == (created["id"], {"title": "90레벨 경험치가 틀려요"})


def test_admin_deletes_answered_report(experiences):
    created = write_report(member_client(), level_90())
    admin = member_client("관리자", is_staff=True)
    admin.patch(f"/report/{created['id']}", {"status": "REJECTED"}, format="json")

    assert admin.delete(f"/report/{created['id']}").status_code == 204
    assert admin.delete(f"/report/{created['id']}").status_code == 404


def test_report_survives_author_withdrawal(experiences):
    member = member_client()
    created = write_report(member, level_90())

    response = member.delete("/auth/me", {"password": "correct-horse-42"}, format="json")

    assert response.status_code == 204, response.json()
    admin = member_client("관리자", is_staff=True)
    assert admin.get(f"/report/{created['id']}").json()["author"] is None


def test_report_keeps_snapshot_after_data_changes(experiences):
    created = write_report(member_client(), level_90())
    Experience.objects.filter(level=90).delete()

    change = member_client("관리자", is_staff=True).get(f"/report/{created['id']}").json()["changes"][0]
    assert (change["label"], change["before"], change["after"]) == ("90레벨", 190000, 10000000)
