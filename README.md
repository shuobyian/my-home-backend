# my-home-backend

물품 제작 비용 계산기 백엔드 (Django + Django REST Framework).
기존 NestJS 서버와 같은 API(URL, 요청/응답 형식, 에러 형식)와 같은 DB 스키마를 사용한다.

## 기술 스택

- Python 3.11, Django 5.2 LTS, Django REST Framework
- PostgreSQL 14 이상 (권장 16)
- gunicorn

## 프로젝트 구조

```
config/                 Django 설정, URL
apps/common/            공통 (Nest 호환 에러 형식, 쿼리 파싱, 숫자 형식, 시퀀스 보정 마이그레이션)
apps/products/          물품(product), 재료(material) — /product
apps/markets/           시세(market) — /market
apps/results/           계산 결과(result) — /result
  calculator.py         핵심 계산 로직 (DB와 무관한 순수 모듈)
  presenters.py         결과 응답 형식 (제작 개수 배율 포함)
apps/experiences/       레벨 경험치(experience), 호두나무 계산 — /experience
tests/                  pytest
```

## 로컬 실행

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # 값 채우기
python manage.py migrate --fake-initial
python manage.py runserver 8123
```

`DJANGO_DEBUG=True`면 `DJANGO_SECRET_KEY` 없이도 실행된다. 운영에서는 반드시 설정한다.

## 테스트

```bash
pytest                                                        # SQLite 메모리 DB
TEST_DATABASE_URL=postgres://postgres:postgres@localhost:5432/postgres pytest   # Postgres
ruff check . && ruff format --check .
```

테스트 설정(`config/test_settings.py`)은 `.env`의 `POSTGRES_*` 값을 쓰지 않는다.

## 기존 NestJS 서버에서 전환하기

1. **PostgreSQL 16으로 업그레이드** — Django 5.2는 PostgreSQL 14 이상만 지원한다 (기존 DB는 13).
   ```bash
   pg_dump -Fc -h <기존 호스트> -U <유저> <DB명> > myhome.dump
   # PostgreSQL 16 서버(또는 postgres:16-alpine 컨테이너, 새 볼륨)를 띄운 뒤
   pg_restore -h <새 호스트> -U <유저> -d <DB명> --no-owner myhome.dump
   ```
   docker-compose의 기존 `postgres_data` 볼륨은 13 데이터라서 16 컨테이너에서 그대로 쓸 수 없다. 덤프를 뜬 다음 새 볼륨에 복원한다.
2. `.env`에 `DJANGO_SECRET_KEY`를 추가한다 (`python -c "import secrets; print(secrets.token_urlsafe(50))"`).
3. `python manage.py migrate --fake-initial`을 실행한다.
   - 테이블이 이미 있으므로 초기 마이그레이션은 적용된 것으로 처리하고, `common.0001_reset_sequences`가 id 시퀀스를 현재 최대 id에 맞춘다.
   - Docker 이미지는 시작할 때 이 명령을 자동으로 실행한다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 헬스 체크 (`Hello World!`) |
| POST | `/product/login` | `{password}` 관리자 비밀번호 확인 |
| GET | `/product?page&size&name` | 물품 목록 (재료 포함) `{totalElements, content}` |
| POST | `/product` | 물품 추가 (재료 포함) |
| POST | `/product/all` | `{products: [...]}` 일괄 추가 (이미 있는 물품은 건너뜀) |
| PUT | `/product` | 물품 수정 (보낸 필드만 수정, 재료는 통째로 교체) |
| DELETE | `/product` | `[id, ...]` 삭제 (재료·결과도 함께 삭제) |
| GET | `/market` | 시세 목록 |
| PUT | `/market` | `[{id, name, price}]` 시세 수정/추가 후 전체 결과 재계산 |
| POST | `/result` | 결과가 없는 물품의 결과 생성 |
| GET | `/result?page&size&name&count&tool&category` | 결과 목록 (`count`개 제작 기준) |
| POST | `/result/calculator` | `{markets: [{name, price}]}` 입력 시세로 미리 계산 (저장 안 함) |
| GET | `/experience` | 레벨별 경험치 |
| GET | `/experience/walnut?presentLevel&presentExperience&objectiveLevel&productionPercent` | 호두나무 수확 횟수와 식물앰플 비용 |

에러 응답은 NestJS와 같은 형식이다: `{"statusCode": 400, "message": "...", "error": "Bad Request"}`

## 계산 로직 (`apps/results/calculator.py`)

물품 레시피를 기본 재료(시세로 사는 재료)까지 펼쳐서 재료별 총 수량과 가격을 구한다.

- 물품/시세를 이름으로 바로 찾는다 (dict). 기존에는 큐에서 꺼낼 때마다 전체 물품 목록을 훑었다.
- 물품마다 펼친 결과를 한 번만 계산해 메모해 두고 재사용한다. 전체 결과 생성·재계산도 물품 수에 비례하는 시간에 끝난다.
- 재료 순서는 기존 BFS와 같다 (얕은 단계 먼저, 같은 단계는 레시피 순서). 물품마다 '단계별 수량'을 메모해서 순서를 맞춘다.
- 입력 데이터를 바꾸지 않는다. 기존에는 재료 객체의 수량을 직접 더해서 같은 요청에서 뒤에 계산되는 물품의 수량이 틀어졌다.
- 잘못된 하위 재료명, 순환 참조, 시세 없는 재료는 무한 루프나 잘못된 저장 대신 400 에러로 알린다.

## 기존 대비 달라진 동작

- 시세 수정(PUT /market) 시 DB의 **전체 시세**로 재계산하고 names/counts/prices/totalPrice를 모두 갱신한다. 결과가 없는 물품은 건너뛴다. 재계산이 실패하면 시세 저장도 취소된다.
- 계산기(POST /result/calculator) 응답의 `id`는 결과 id다 (기존에는 물품 id로 덮어썼다). 결과는 레벨, 이름 순으로 정렬된다.
- 물품 삭제 시 재료와 결과도 함께 삭제된다 (기존에는 FK 제약 때문에 실패했다).
- 일괄 추가(POST /product/all)에 이미 있는 물품이 섞여 있어도 새 물품만 추가한다 (기존에는 500 에러). 같은 이름이 목록에 두 번 있으면 400을 응답한다.
- 쓰기 API는 트랜잭션으로 처리한다. 중간에 실패하면 전부 취소된다.
- 경험치 계산은 레벨마다 쿼리하던 것을 한 번의 쿼리로 바꿨다. 목표 레벨이 현재 레벨 이하이거나, 경험치 데이터가 없는 레벨이 있으면 400을 응답한다.
- 잘못된 쿼리 값(숫자가 아닌 page/size/count 등), 존재하지 않는 tool/category, 콤마가 들어간 이름은 400을 응답한다.
- 서버에 `PASSWORD`가 설정되지 않았으면 로그인할 수 없다 (기존에는 비밀번호 없이 요청하면 통과했다).
- 응답 숫자의 부동소수점 오차를 정리한다 (예: `0.30000000000000004` → `0.3`).
