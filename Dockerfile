FROM python:3.11-slim

ENV TZ=Asia/Seoul \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /usr/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# .dockerignore에 적힌 파일을 제외하고 복사한다. 기존 Nest 배포처럼 .env도 이미지에 들어간다.
COPY . .

EXPOSE 8123

# Render처럼 PORT를 정해 주는 곳에서는 그 포트로, 아니면 8123으로 띄운다.
# 기존 TypeORM(synchronize) DB에서는 테이블이 이미 있으므로 --fake-initial로 초기 마이그레이션을 건너뛴다.
CMD ["sh", "-c", "python manage.py migrate --fake-initial --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8123} --workers ${GUNICORN_WORKERS:-2} --access-logfile -"]
