import pytest
from django.db.models import Max

from apps.experiences.models import Experience

pytestmark = pytest.mark.django_db


def test_list_experiences(client, experiences):
    body = client.get("/experience").json()

    assert body[0]["level"] == 55
    assert [row["level"] for row in body] == sorted(row["level"] for row in body)
    assert set(body[0]) == {"id", "level", "amount"}


def test_walnut_next_level(client, experiences, ample):
    response = client.get("/experience/walnut", {"presentLevel": 60, "presentExperience": 1000})

    body = response.json()
    assert response.status_code == 200
    # Lv.60 경험치 160000 - 1000, 호두 1회 = int(65340 * 1.6) = 104544
    assert body["remindExperience"] == 159000
    assert body["remindCount"] == 1
    assert body["ample"]["result"]["materials"] == [{"name": "호두", "price": 200, "count": 2}]
    assert body["ample"]["result"]["craftingPrice"] == 1000


def test_walnut_multiple_levels(client, experiences, ample):
    body = client.get("/experience/walnut", {"presentLevel": 60, "objectiveLevel": 63, "productionPercent": 0}).json()

    assert body["remindExperience"] == 160000 + 161000 + 162000
    assert body["remindCount"] == int(483000 / 65340)


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"presentLevel": 54}, "호두나무는 55렙 이상부터 생산 가능합니다. 레벨업하고 오세요."),
        ({"presentLevel": 60, "objectiveLevel": 113}, "Lv.112이 만렙입니다."),
        ({"presentLevel": 112}, "Lv.112이 만렙입니다."),
        ({"presentLevel": 60, "objectiveLevel": 60}, "목표 레벨은 현재 레벨보다 높아야 합니다."),
        (
            {"presentLevel": 60, "presentExperience": 160000},
            "입력한 경험치가 현재 레벨 경험치보다 많습니다. 다시 설정해 주세요.",
        ),
        ({}, "presentLevel 값이 필요합니다."),
        ({"presentLevel": "abc"}, "presentLevel 값은 숫자여야 합니다."),
        ({"presentLevel": 55, "presentExperience": -1}, "presentExperience 값은 0 이상이어야 합니다."),
        ({"presentLevel": 55, "productionPercent": 10001}, "productionPercent 값은 10000 이하여야 합니다."),
        ({"presentLevel": "55.5"}, "presentLevel 값은 정수여야 합니다."),
    ],
)
def test_walnut_errors(client, experiences, ample, params, message):
    response = client.get("/experience/walnut", params)

    assert response.status_code == 400
    assert response.json()["message"] == message


def test_walnut_without_ample_result(client, experiences):
    response = client.get("/experience/walnut", {"presentLevel": 60})

    assert response.status_code == 400


def test_list_experiences_sorted_by_level_not_insert_order(client):
    # experiences fixture와 같이 쓰면 레벨이 중복되므로 직접 만든다. 높은 레벨부터 넣는다.
    Experience.objects.bulk_create(Experience(level=level, amount=level) for level in range(112, 54, -1))

    body = client.get("/experience").json()

    assert [row["level"] for row in body] == list(range(55, 113))
    # 가장 나중에 넣은 Lv.55가 맨 앞에 온다 (id 순이 아니라 레벨 순).
    assert body[0]["id"] == Experience.objects.aggregate(Max("id"))["id__max"]


def test_walnut_missing_experience_levels_message(client):
    Experience.objects.bulk_create(Experience(level=level, amount=100000 + level * 1000) for level in range(55, 61))

    response = client.get("/experience/walnut", {"presentLevel": 59, "objectiveLevel": 63})

    assert response.status_code == 400
    assert response.json()["message"] == "경험치 정보가 없는 레벨이 있습니다. (Lv.61, 62)"


def test_walnut_without_ample_result_message(client, experiences):
    response = client.get("/experience/walnut", {"presentLevel": 60})

    assert response.status_code == 400
    assert response.json()["message"] == "식물앰플-중급 가속 결과 정보가 없습니다."


def test_walnut_zero_remind_count(client, experiences, ample):
    response = client.get(
        "/experience/walnut", {"presentLevel": 55, "presentExperience": 154999, "productionPercent": 0}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["remindExperience"] == 1
    assert body["remindCount"] == 0
    # count=0에서 예외 없이 모두 0이 나오는 것을 고정한다
    result = body["ample"]["result"]
    assert result["totalPrice"] == 0
    assert type(result["totalPrice"]) is int
    assert result["craftingPrice"] == 0
    assert type(result["craftingPrice"]) is int
    assert result["product"]["craftingPrice"] == 1000
    assert result["materials"] == [{"name": "호두", "price": 0, "count": 0}]
    assert result["product"]["materials"] == [{"name": "호두", "basic": True, "count": 0}]


def test_walnut_fractional_production_percent(client, experiences, ample):
    # Lv.55~61 경험치 합 1106000 - 58000 = 1048000, 호두 1회 = int(65340 * 1.605) = 104870 → 9회
    # (60%로 잘리면 int(65340 * 1.6) = 104544 → 10회)
    response = client.get(
        "/experience/walnut",
        {"presentLevel": 55, "objectiveLevel": 62, "presentExperience": 58000, "productionPercent": "60.5"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["remindExperience"] == 1048000
    assert body["remindCount"] == 9


def test_walnut_multi_level_present_experience_check(client, experiences, ample):
    # 여러 레벨을 계산할 때도 현재 레벨(Lv.60 = 160000)의 경험치와 비교한다.
    response = client.get("/experience/walnut", {"presentLevel": 60, "objectiveLevel": 62, "presentExperience": 160000})

    assert response.status_code == 400
    assert response.json()["message"] == "입력한 경험치가 현재 레벨 경험치보다 많습니다. 다시 설정해 주세요."
