"""my-home-backend Django 설정.

환경변수(.env)는 기존 NestJS 서버와 같은 키를 그대로 사용한다.
"""

from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
if (BASE_DIR / ".env").exists():
    # 이미 설정된 환경변수가 .env 값보다 우선한다.
    environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DJANGO_DEBUG", default=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY 환경변수를 설정해 주세요.")
    SECRET_KEY = "django-insecure-local-development-only"

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "apps.common",
    "apps.accounts",
    "apps.products",
    "apps.markets",
    "apps.results",
    "apps.experiences",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "USER": env("POSTGRES_USER", default="postgres"),
        "PASSWORD": env("POSTGRES_PASSWORD", default=""),
        "NAME": env("POSTGRES_NAME", default="postgres"),
        "CONN_MAX_AGE": env.int("POSTGRES_CONN_MAX_AGE", default=60),
        # Neon처럼 쉬는 동안 연결을 끊는 DB에서도 끊긴 연결을 다시 쓰지 않도록 요청마다 확인한다.
        "CONN_HEALTH_CHECKS": True,
    }
}

# Neon 같은 관리형 DB는 SSL 접속이 필수다 (예: POSTGRES_SSLMODE=require). 비어 있으면 libpq 기본값을 쓴다.
if POSTGRES_SSLMODE := env("POSTGRES_SSLMODE", default=""):
    DATABASES["default"]["OPTIONS"] = {"sslmode": POSTGRES_SSLMODE}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# 로그인 토큰 유효 기간. 지나면 다시 로그인해야 한다.
AUTH_TOKEN_TTL = timedelta(days=7)

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# NestJS 라우팅처럼 끝의 슬래시 유무와 관계없이 같은 URL로 처리한다 (urls에서 처리).
APPEND_SLASH = False

# 기존 body-parser limit(50mb)과 동일 (JSON 본문은 apps.common.parsers.LimitedJSONParser가 적용)
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (*default_headers, "*")

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["apps.common.parsers.LimitedJSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.BearerTokenAuthentication"],
    # 쓰기 API는 뷰마다 관리자 권한(apps.common.permissions.IsAdminOrReadOnly 등)을 건다.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    # throttle_scope가 있는 뷰(로그인·가입·비밀번호 확인)만 횟수를 제한한다.
    # ponytail: 기록은 프로세스 메모리(LocMemCache)라 gunicorn worker마다 따로 센다.
    # 클라이언트 구분은 X-Forwarded-For 전체 값이라 위조로 피할 수 있다.
    # 정확히 막아야 하면 공유 캐시(DB·Redis)로 옮기고, 프록시 단계 수를 확인해 NUM_PROXIES를 정한다.
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"auth": "10/min", "signup": "10/hour"},
    "EXCEPTION_HANDLER": "apps.common.exceptions.nest_exception_handler",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
