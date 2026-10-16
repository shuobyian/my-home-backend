"""테스트 전용 설정.

기본은 SQLite 메모리 DB를 쓰고, TEST_DATABASE_URL을 주면 해당 DB(예: Postgres)로 테스트한다.
운영 .env의 POSTGRES_* 값으로는 절대 테스트 DB를 만들지 않는다.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")

from config.settings import *  # noqa: E402,F403
from config.settings import env  # noqa: E402

LOGIN_PASSWORD = "test-password"

DATABASES = {
    "default": env.db_url("TEST_DATABASE_URL", default="sqlite://:memory:"),
}
