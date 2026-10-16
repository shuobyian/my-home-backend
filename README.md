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
apps/common/            공통 (Nest 호환 에러 형식, 쿼리 파싱, 숫자 형식, 관리자 로그인(/product/login), 시퀀스 보정 마이그레이션)
apps/products/          물품(product), 재료(material) — /product
  recipes.py            레시피 읽기·검증 (DB에서 레시피를 읽어 계산기로 펼칠 수 있는지 확인)
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
pytest                                  # SQLite 메모리 DB
ruff check . && ruff format --check .
```

Postgres로 돌릴 때는 개발 DB(docker-compose, 실제 데이터가 있음) 대신 별도 포트의 PostgreSQL 16 임시 컨테이너를 쓴다.

```bash
docker run --rm -d --name myhome-test-pg -p 127.0.0.1:55432:5432 -e POSTGRES_PASSWORD=postgres postgres:16-alpine
until docker exec myhome-test-pg pg_isready -U postgres; do sleep 1; done
TEST_DATABASE_URL=postgres://postgres:postgres@127.0.0.1:55432/postgres pytest
docker stop myhome-test-pg
```

잠금(select_for_update)과 트랜잭션 테스트(`tests/test_postgres_locking.py`)는 Postgres에서만 돈다. 리팩터링 전후로 한 번씩 돌린다.

테스트 설정(`config/test_settings.py`)은 `.env`의 `POSTGRES_*` 값을 쓰지 않는다. 운영 `.env` 값으로 테스트하지 않는다.

## 기존 NestJS 서버에서 전환하기

### 0. 전환 전 점검 (기존 DB에서 실행)

레시피가 깨진 물품이 있으면 전환 후 시세 수정(PUT /market)이 400으로 막힌다. 아래 쿼리 결과가 없어야 한다.

```sql
-- 물품으로 존재하지 않는 하위 물품
SELECT p.name AS product, m.name AS material FROM material m JOIN product p ON p.id = m.product_id
LEFT JOIN product sub ON sub.name = m.name WHERE NOT m.basic AND sub.id IS NULL;
-- 시세가 없는 기본 재료
SELECT p.name AS product, m.name AS material FROM material m JOIN product p ON p.id = m.product_id
LEFT JOIN market k ON k.name = m.name WHERE m.basic AND k.id IS NULL;
-- 새 서버가 거절하는 값: 수량 0 이하, 허용하지 않는 tool/category, 콤마가 들어간 이름
SELECT * FROM material WHERE count <= 0;
SELECT id, name, tool, category FROM product
WHERE tool NOT IN ('WOOD','FIRE_PIT','SEWING_MACHINE','LEATHER','BRAZIER','POTTERY_WHEEL','ALCHEMY_KETTLE','MIMI')
   OR category NOT IN ('NORMAL','EVENT');
SELECT 'product' AS t, name FROM product WHERE name LIKE '%,%'
UNION ALL SELECT 'material', name FROM material WHERE name LIKE '%,%'
UNION ALL SELECT 'market', name FROM market WHERE name LIKE '%,%';
```

마지막 세 쿼리에 걸리는 값이 남아 있으면 전환 후 그 물품을 수정(PUT /product)할 때 400이 나므로 미리 고친다.

### 1. PostgreSQL 16으로 업그레이드

Django 5.2는 PostgreSQL 14 이상만 지원한다 (기존 DB는 13). docker-compose는 새 볼륨 `postgres16_data`를 쓰고,
기존 13 데이터 볼륨 `postgres_data`는 롤백용으로 남겨 둔다 (지우지 않는다).

변수(`$POSTGRES_USER` 등)는 컨테이너 안에서 펼쳐지도록 `sh -c '...'`로 감싼다 (호스트 셸에는 .env 값이 없다).

```bash
# (1) 아직 기존 코드(postgres:13)인 상태에서: Nest 서버를 멈추고 덤프한다
docker compose exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_NAME"' > myhome.dump

# (2) 새 코드를 받은 뒤 16을 빈 볼륨으로 띄우고, 초기화가 끝날 때까지 기다린다
docker compose up -d postgres
until docker compose exec -T postgres sh -c 'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER"'; do sleep 1; done

# (3) POSTGRES_NAME이 POSTGRES_USER와 다르면 DB를 먼저 만든다 (같으면 이미 있어서 에러가 나도 무시)
docker compose exec -T postgres sh -c 'createdb -h 127.0.0.1 -U "$POSTGRES_USER" "$POSTGRES_NAME"'

# (4) 복원
docker compose exec -T postgres sh -c 'pg_restore -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_NAME" --no-owner' < myhome.dump
```

DB를 따로 운영한다면 같은 방식으로 `pg_dump` → PostgreSQL 16 서버에 `pg_restore` 한다.

### 2. 설정과 마이그레이션

1. `.env`에 `DJANGO_SECRET_KEY`를 추가한다 (`python -c "import secrets; print(secrets.token_urlsafe(50))"`).
2. `python manage.py migrate --fake-initial`
   - 테이블이 이미 있으므로 초기 마이그레이션은 적용된 것으로 처리한다(FAKED).
   - `common.0001_reset_sequences`가 id 시퀀스를 현재 최대 id에 맞추고, `common.0002_material_product_index`가 기존 DB에 없던 `material.product_id` 인덱스를 만든다.
   - Docker 이미지는 시작할 때 이 명령을 자동으로 실행한다.
3. `python manage.py recalculate_results --create-missing` — **전환 직후 한 번 실행한다.**
   기존 서버의 시세 수정은 결과를 물품 id로 갱신해서 다른 물품의 결과 행을 덮어썼다. 그래서 저장된 결과가 틀려 있을 수 있다.
   이 명령은 모든 결과를 현재 시세로 다시 계산하고, 결과가 없는 물품의 결과를 만든다. 실패하면 아무것도 저장하지 않고 원인 물품을 알려 준다.

### 롤백

기존 DB에서 전환한 경우에만 Nest 서버로 되돌릴 수 있다 (Django는 기존 테이블 구조를 바꾸지 않는다).
Django `migrate`로 새로 만든 DB에는 Nest(`synchronize: true`)를 붙이지 않는다. 붙이면 Nest가 Django의 FK와 인덱스를 지우고 다시 만든다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 헬스 체크 (`Hello World!`) |
| POST | `/product/login` | `{password}` 관리자 비밀번호 확인 |
| GET | `/product?page&size&name` | 물품 목록 (재료 포함) `{totalElements, content}` |
| POST | `/product` | 물품 추가 (재료 포함) |
| POST | `/product/all` | `{products: [...]}` 일괄 추가 (이미 있는 물품은 건너뜀) |
| PUT | `/product` | 물품 수정 (보낸 필드만 수정, 재료는 통째로 교체) |
| DELETE | `/product` | `{ids: [...]}` 또는 `[id, ...]` 삭제 (재료·결과도 함께 삭제) |
| GET | `/market` | 시세 목록 |
| PUT | `/market` | `[{id, name, price}]` 시세 수정/추가 후 전체 결과 재계산 |
| POST | `/result` | 결과가 없는 물품의 결과 생성 |
| GET | `/result?page&size&name&count&tool&category` | 결과 목록 (`count`개 제작 기준) |
| POST | `/result/calculator` | `{markets: [{name, price}]}` 입력 시세로 미리 계산 (저장 안 함, price가 null이면 0원) |
| GET | `/experience` | 레벨별 경험치 |
| GET | `/experience/walnut?presentLevel&presentExperience&objectiveLevel&productionPercent` | 호두나무 수확 횟수와 식물앰플 비용 |

요청 본문은 JSON만 받는다. 에러 응답은 NestJS와 같은 형식이다: `{"statusCode": 400, "message": "...", "error": "Bad Request"}`

## 계산 로직 (`apps/results/calculator.py`)

물품 레시피를 기본 재료(시세로 사는 재료)까지 펼쳐서 재료별 총 수량과 가격을 구한다.

- 물품/시세를 이름으로 바로 찾는다 (dict). 기존에는 큐에서 꺼낼 때마다 전체 물품 목록을 훑었다.
- 물품마다 펼친 결과를 한 번만 계산해 메모해 두고 재사용한다. 전체 결과 생성·재계산도 물품 수에 비례하는 시간에 끝난다.
- 재료 순서는 기존 BFS와 같다 (얕은 단계 먼저, 같은 단계는 레시피 순서). 물품마다 '단계별 수량'을 메모해서 순서를 맞춘다.
- 입력 데이터를 바꾸지 않는다. 기존에는 재료 객체의 수량을 직접 더해서 같은 요청에서 뒤에 계산되는 물품의 수량이 틀어졌다.
- 잘못된 하위 재료명, 순환 참조, 시세 없는 재료는 무한 루프나 잘못된 저장 대신 400 에러로 알린다.
- 레시피에 같은 기본 재료가 여러 줄 있으면 한 줄로 합친다 (기존에는 최상위 레시피에서만 줄이 나뉘었다).

## 기존 대비 달라진 동작

프론트엔드(my-home-frontend)가 쓰는 정상 요청의 응답 형식은 그대로다. 응답에 키가 추가된 곳만 있다
(결과 항목의 최상위 `category`, 물품 추가·수정 응답의 `id`/`materials`).

**계산·저장**
- 시세 수정(PUT /market) 시 DB의 **전체 시세**로 재계산하고 names/counts/prices/totalPrice를 모두 갱신한다. 결과가 없는 물품은 건너뛴다. 재계산이 실패하면 시세 저장도 취소된다.
- 계산기(POST /result/calculator) 응답의 `id`는 결과 id다 (기존에는 물품 id로 덮어썼다). 결과는 레벨, 이름 순으로 정렬된다.
- 결과 응답의 `totalPrice`는 재료 가격의 합이다. totalPrice 컬럼(정수)에는 반올림(.5 올림)해 저장한다. 기존에는 합계가 소수면 저장하다 500이 났다.
  저장할 합계가 정수 컬럼 범위(약 21억)를 넘으면 결과 생성·재계산이 400이다. 저장하지 않는 계산기에는 이 제한이 없다.
- 응답 숫자의 부동소수점 오차를 정리한다 (예: `0.30000000000000004` → `0.3`). 재료가 없는 물품의 결과 materials는 `[]`다.

**물품**
- 물품 추가·수정 시 레시피를 검증한다. 존재하지 않는 하위 물품이나 순환 참조가 있으면 400이다 (일괄 추가는 같은 업로드 안의 물품을 참조해도 된다).
- 물품 이름을 바꾸면 그 물품을 재료로 쓰는 다른 레시피의 재료 이름도 함께 바뀐다.
- 물품 삭제 시 재료와 결과도 함께 삭제된다 (기존에는 FK 제약 때문에 실패했다). 다른 물품의 재료로 쓰이는 물품은 400으로 거절한다.
- 삭제 본문으로 프론트엔드가 보내는 `{ids: [...]}`도 받는다 (기존 서버는 이 형식을 처리하지 못했다).
- 일괄 추가(POST /product/all)에 이미 있는 물품이 섞여 있어도 새 물품만 추가한다 (기존에는 500). 이미 있는 물품의 행은 검증하지 않고 건너뛴다. 같은 이름이 목록에 두 번 있으면 400이다.
- tool은 프론트엔드 목록과 같은 8개 값(`MIMI` 포함), category는 `NORMAL`/`EVENT`만 받는다 (기존에는 아무 문자열이나 저장했다).
- `category`를 보내지 않으면 `NORMAL`로 저장한다 (기존에는 500).
- 재료 수량은 0보다 크고 1,000,000 이하인 유한한 숫자여야 한다 (NaN/Infinity 거절).

**입력 검증 (기존 500 또는 잘못된 200 → 400)**
- 숫자가 아니거나 소수·음수·범위를 넘는 page/size/count, 정수 컬럼 범위를 넘는 숫자, 존재하지 않는 tool/category, 콤마가 들어간 이름.
- 빈 쿼리 값(`tool=`, `count=`)은 보내지 않은 것으로 본다. 이름 검색의 `%`, `_`는 문자 그대로 검색한다.
- 계산기 입력에 같은 시세 이름이 두 번 있거나, 가격이 음수·Infinity이거나, price 키가 없으면 400이다 (price가 null이면 0원).
- 시세 수정(PUT /market)에 price가 null이거나 소수인 항목이 있으면 400이다 (기존에는 500).
- 호두나무 계산: presentLevel 누락·문자, 목표 레벨 ≤ 현재 레벨, 현재 레벨 112(만렙), 경험치 데이터가 없는 레벨,
  현재 경험치가 현재 레벨 경험치 이상(여러 레벨을 계산할 때도), 소수·음수 경험치, 0~10000 밖의 생산 증가율이면 400이다.
  남은 수확 횟수가 0이면 ample의 craftingPrice는 null 대신 0이다.

**기타**
- 쓰기 API는 트랜잭션으로 처리한다. 중간에 실패하면 전부 취소된다.
- 경험치 계산은 레벨마다 쿼리하던 것을 한 번의 쿼리로 바꿨다.
- 서버에 `PASSWORD`가 설정되지 않았으면 로그인할 수 없다 (기존에는 비밀번호 없이 요청하면 통과했다).
- 요청 본문 50MB 제한이 실제로 적용된다 (413). 폼(urlencoded) 본문은 받지 않는다 (415).
- 지원하지 않는 HTTP 메서드는 404 대신 405다.
