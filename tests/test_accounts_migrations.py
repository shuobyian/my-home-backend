"""accounts 데이터 마이그레이션. 이미 가입한 회원이 새 필수 컬럼을 채운 채로 넘어가는지 본다."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE_NICKNAME = [("accounts", "0001_initial")]
WITH_NICKNAME = [("accounts", "0002_user_nickname")]


def migrate(targets):
    """targets 상태로 옮기고 그 시점의 모델(apps)을 돌려준다."""
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    executor.loader.build_graph()
    return executor.loader.project_state(targets).apps


@pytest.fixture
def before_nickname():
    old_apps = migrate(BEFORE_NICKNAME)
    yield old_apps
    # 다음 테스트를 위해 최신 스키마로 되돌린다.
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def test_existing_admin_gets_admin_nickname_and_members_get_username(before_nickname):
    User = before_nickname.get_model("accounts", "User")
    AuthToken = before_nickname.get_model("accounts", "AuthToken")
    User.objects.create(username="admin", is_staff=True, is_superuser=True)
    member = User.objects.create(username="member")
    User.objects.create(username="a" * 30)
    # 회원을 가리키는 토큰이 있어도(외래 키) 같은 트랜잭션에서 제약을 추가할 수 있어야 한다.
    AuthToken.objects.create(user=member, digest="0" * 64, expires_at=timezone.now())

    User = migrate(WITH_NICKNAME).get_model("accounts", "User")

    assert dict(User.objects.values_list("username", "nickname")) == {
        "admin": "관리자",
        "member": "member",
        "a" * 30: "a" * 20,
    }
