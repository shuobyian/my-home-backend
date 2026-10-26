"""common 마이그레이션. 운영 DB처럼 제약 없이 넘겨받은 market에 빠진 제약을 채우는지 본다."""

import pytest
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor

from apps.markets.models import Market

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="Postgres 전용"),
]

BEFORE_MARKET_CONSTRAINTS = [("common", "0002_material_product_index"), ("inventories", "0001_initial")]

# 운영 DB(Neon)의 market: 제약·인덱스·기본값 없이 전부 nullable이고 name이 text다.
PRODUCTION_MARKET = "CREATE TABLE market (id integer, name text, price integer)"

# TypeORM이 만든 개발 DB의 market: 이름만 다를 뿐 제약은 다 있다.
TYPEORM_MARKET = """
CREATE TABLE market (
    id serial NOT NULL,
    name varchar(255) NOT NULL,
    price integer NOT NULL,
    CONSTRAINT "PK_1e9a2963edfd331d92018e3abac" PRIMARY KEY (id),
    CONSTRAINT "UQ_1aeb3f3714d39ebc4697c220e97" UNIQUE (name)
)
"""


def migrate(targets=None):
    """targets 상태로 옮긴다. 없으면 최신 스키마로 옮긴다."""
    executor = MigrationExecutor(connection)
    executor.migrate(targets or executor.loader.graph.leaf_nodes())


def fetchall(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall() if cursor.description else None


def replace_market(ddl):
    """market 제약을 채우기 전으로 되돌리고 market을 ddl 모양으로 다시 만든다. id 사이에 빈 번호가 있다."""
    migrate(BEFORE_MARKET_CONSTRAINTS)
    fetchall("DROP TABLE market")
    fetchall(ddl)
    fetchall("INSERT INTO market (id, name, price) VALUES (1, '나무', 10), (2, '못', 5), (5, '천', 7)")


def market_keys():
    return fetchall(
        "SELECT conname, contype FROM pg_constraint"
        " WHERE conrelid = 'market'::regclass AND contype IN ('p', 'u') ORDER BY contype, conname"
    )


def has_inventory_market_foreign_key():
    return bool(
        fetchall(
            "SELECT 1 FROM pg_constraint WHERE conrelid = 'inventories_inventoryitem'::regclass"
            " AND contype = 'f' AND confrelid = 'market'::regclass"
        )
    )


@pytest.fixture
def restore_market():
    yield
    # 다음 테스트를 위해 market을 Django가 만든 모양으로 다시 만들고 최신 스키마로 되돌린다.
    migrate([("markets", None)])
    migrate()


def test_new_database_keeps_django_constraints():
    assert market_keys() == [("market_pkey", "p"), ("market_name_key", "u")]
    assert has_inventory_market_foreign_key()


@pytest.mark.usefixtures("restore_market")
def test_adds_missing_constraints_to_production_market():
    replace_market(PRODUCTION_MARKET)

    migrate()

    assert market_keys() == [("market_pkey", "p"), ("market_name_key", "u")]
    assert fetchall(
        "SELECT column_name, data_type, character_maximum_length, is_nullable, is_identity"
        " FROM information_schema.columns WHERE table_name = 'market' ORDER BY ordinal_position"
    ) == [
        ("id", "integer", None, "NO", "YES"),
        ("name", "character varying", 255, "NO", "NO"),
        ("price", "integer", None, "NO", "NO"),
        # markets.0002가 제약을 채운 뒤 분류 칸을 더한다.
        ("group", "character varying", 255, "NO", "NO"),
    ]
    # update_markets처럼 bulk_create로 추가해도 지금 있는 최대 id 다음 번호를 받는다.
    (created,) = Market.objects.bulk_create([Market(name="돌", price=3)])
    assert created.id == 6
    # 같은 이름의 시세는 DB가 막는다 (update_markets가 이 에러로 "이미 존재하는 시세 이름"을 알린다).
    with pytest.raises(IntegrityError):
        Market.objects.create(name="나무", price=1)
    assert has_inventory_market_foreign_key()


@pytest.mark.usefixtures("restore_market")
def test_keeps_existing_typeorm_constraints():
    replace_market(TYPEORM_MARKET)

    migrate()

    assert market_keys() == [("PK_1e9a2963edfd331d92018e3abac", "p"), ("UQ_1aeb3f3714d39ebc4697c220e97", "u")]
    assert Market.objects.create(name="돌", price=3).id == 6
    assert has_inventory_market_foreign_key()
