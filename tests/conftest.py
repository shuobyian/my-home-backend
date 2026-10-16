import pytest
from rest_framework.test import APIClient

from apps.experiences.models import Experience
from apps.markets.models import Market
from tests.factories import make_product


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def catalog(db):
    """시세 3개, 물품 3개(판자 → 식탁, 의자)로 된 기본 데이터."""
    Market.objects.bulk_create([Market(name="나무", price=10), Market(name="못", price=5), Market(name="천", price=7)])
    plank = make_product("판자", [("나무", True, 3)], level=1, crafting_price=50)
    table = make_product("식탁", [("판자", False, 2), ("못", True, 4)], level=5, crafting_price=200, tool="FIRE_PIT")
    chair = make_product("의자", [("판자", False, 1), ("천", True, 2)], level=3, crafting_price=120, category="EVENT")
    return {"판자": plank, "식탁": table, "의자": chair}


@pytest.fixture
def experiences(db):
    Experience.objects.bulk_create(Experience(level=level, amount=100000 + level * 1000) for level in range(55, 113))
