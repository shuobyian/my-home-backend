"""inventories 마이그레이션. 운영 DB처럼 market에 기본키 제약이 없어도 적용되어야 한다."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)
postgres_only = pytest.mark.skipif(connection.vendor != "postgresql", reason="Postgres 전용")


def migrate(targets=None):
    """targets 상태로 옮긴다. 없으면 최신 스키마로 옮긴다."""
    executor = MigrationExecutor(connection)
    executor.migrate(targets or executor.loader.graph.leaf_nodes())


def execute(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchone() if cursor.description else None


@postgres_only
def test_applies_when_market_has_no_primary_key():
    # TypeORM에서 넘겨받은 운영 DB의 market에는 id 기본키 제약이 없어서, DB 외래 키를 걸면 배포가 실패했다.
    migrate([("inventories", None)])
    (primary_key,) = execute("SELECT conname FROM pg_constraint WHERE conrelid = 'market'::regclass AND contype = 'p'")
    execute(f'ALTER TABLE market DROP CONSTRAINT "{primary_key}"')
    try:
        migrate([("inventories", "0001_initial")])
    finally:
        # 다음 테스트를 위해 기본키를 되살리고 최신 스키마로 되돌린다.
        execute("ALTER TABLE market ADD PRIMARY KEY (id)")
        migrate()
