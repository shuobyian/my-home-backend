"""markets 마이그레이션. 지금 있는 시세를 이름으로 분류하는지 본다."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE_GROUP = [("markets", "0001_initial")]
AFTER_GROUP = [("markets", "0002_market_group")]


def migrate(targets=None):
    """targets 상태로 옮긴다. 없으면 최신 스키마로 옮긴다."""
    executor = MigrationExecutor(connection)
    executor.migrate(targets or executor.loader.graph.leaf_nodes())
    return executor


def market_model(executor, targets):
    """targets 시점의 Market 모델."""
    return executor.loader.project_state(targets).apps.get_model("markets", "Market")


def test_fills_group_by_name_and_leaves_unknown_as_etc():
    executor = migrate(BEFORE_GROUP)
    try:
        old_market = market_model(executor, BEFORE_GROUP)
        old_market.objects.bulk_create(old_market(name=name, price=1) for name in ["밀", "철", "이스터 에그", "금화"])
        executor = migrate(AFTER_GROUP)
        groups = dict(market_model(executor, AFTER_GROUP).objects.values_list("name", "group"))
    finally:
        # 다음 테스트를 위해 최신 스키마로 되돌린다.
        migrate()

    assert groups == {"밀": "CROP", "철": "MINERAL", "이스터 에그": "EVENT", "금화": "ETC"}
