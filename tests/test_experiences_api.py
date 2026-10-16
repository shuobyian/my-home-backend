import pytest

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
    ],
)
def test_walnut_errors(client, experiences, ample, params, message):
    response = client.get("/experience/walnut", params)

    assert response.status_code == 400
    assert response.json()["message"] == message


def test_walnut_without_ample_result(client, experiences):
    response = client.get("/experience/walnut", {"presentLevel": 60})

    assert response.status_code == 400
