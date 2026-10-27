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
apps/common/            공통 (Nest 호환 에러 형식, 쿼리 파싱, 숫자 형식, 관리자 권한, 시퀀스 보정 마이그레이션)
apps/accounts/          회원(user), 로그인 토큰 — /auth
apps/products/          물품(product), 재료(material) — /product
  recipes.py            레시피 읽기 (전체 레시피와 물품 id를 쿼리 2번으로 계산기 입력 형태로 읽는다)
apps/markets/           시세(market) — /market
apps/results/           계산 결과(result) — /result, 데이터 점검 — /catalog/check
  calculator.py         핵심 계산 로직 (DB와 무관한 순수 모듈)
  diagnosis.py          카탈로그 진단 (차단 문제를 한 번에 모두 찾는 순수 모듈)
  sync.py               시세·물품·결과 연결 (전역 잠금, 쓰기 전후 진단, 결과 동기화, 데이터 점검)
  presenters.py         결과·점검 응답 형식 (제작 개수 배율 포함)
apps/experiences/       레벨 경험치(experience), 호두나무 계산 — /experience
apps/inventories/       회원별 보유 재료(기초 재료 개수) — /inventory
tests/                  pytest
```

## 로컬 실행

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # 값 채우기
python manage.py migrate --fake-initial
python manage.py createsuperuser   # 관리자 계정 (물품·시세 수정용)
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

잠금(select_for_update)과 트랜잭션 테스트(`tests/test_postgres_locking.py`)는 대부분 Postgres에서만 돈다. 리팩터링 전후로 한 번씩 돌린다.

테스트 설정(`config/test_settings.py`)은 `.env`의 `POSTGRES_*` 값을 쓰지 않는다. 운영 `.env` 값으로 테스트하지 않는다.

## 무료 배포 (Render + Neon)

웹 서버는 Render 무료 Web Service(Docker), DB는 Neon 무료 Postgres를 쓴다. 프론트엔드는 Vercel에 올린다(my-home-frontend README 참고).

- Render 무료 인스턴스는 15분 동안 요청이 없으면 잠들고, 다음 요청 때 깨어나는 데 1분 정도 걸린다.
- Neon 무료 플랜은 저장 공간 0.5GB, 월 100 compute-hours이며, 쉬다가 첫 접속 때 몇 초 콜드스타트가 있다.
- 무료 플랜 조건은 자주 바뀌므로 각 서비스의 요금 페이지를 확인한다.

### 1. Neon DB 만들기

1. [Neon](https://neon.com)에서 프로젝트를 만든다. 리전은 Asia Pacific(Singapore)으로 Render와 맞춘다. Postgres 버전은 16 이상.
2. Connection string에서 host, user, password, database를 확인한다. **Connection pooling을 끈 direct 주소**(`-pooler`가 없는 host)를 쓴다.
   Django가 연결을 유지(`CONN_MAX_AGE`)하고 `select_for_update` 트랜잭션을 쓰므로 PgBouncer를 거치지 않는다.

### 2. 기존 데이터 옮기기

기존 서버(EC2)의 DB를 덤프해서 Neon에 복원한다. 로컬의 `pg_restore`는 Neon과 같거나 더 높은 버전이어야 한다.

```bash
# 기존 서버에서
docker compose exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_NAME"' > myhome.dump

# Neon으로 복원 (<...>는 Neon 접속 정보)
pg_restore --no-owner --no-acl -d "postgresql://<user>:<password>@<host>/<database>?sslmode=require" myhome.dump
```

덤프에는 `django_migrations` 테이블도 들어 있으므로 복원 후 컨테이너가 시작할 때 실행하는 `migrate --fake-initial`은 새로 적용할 것만 적용한다.
데이터 없이 새로 시작한다면 복원을 건너뛴다. 빈 DB에는 `migrate`가 테이블을 만든다.

### 3. Render 웹 서버 만들기

1. Render 대시보드에서 **New > Blueprint**를 누르고 이 저장소를 고른다. `render.yaml`대로 서비스가 만들어진다.
2. 입력하라고 나오는 값(`POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_NAME`)을 채운다.
   `DJANGO_SECRET_KEY`는 Render가 만들어 준다.
3. 배포가 끝나면 `https://<서비스 이름>.onrender.com/`에서 `Hello World!`가 나오는지 확인한다.
4. 데이터를 옮겼다면 결과를 한 번 맞춘다. Render의 Shell 탭(무료 플랜에서 안 되면 로컬에서 Neon 접속 정보로)에서
   `python manage.py recalculate_results --create-missing`(엄격 모드)을 실행하거나, 관리자 계정을 만든 뒤
   관리 화면 '데이터 점검 → 결과 다시 맞추기'를 누른다. 차이는 아래 '2. 설정과 마이그레이션'의 3번을 본다.
5. 관리자 계정을 만든다. Render의 Shell 탭(안 되면 로컬에서 `.env`에 Neon 접속 정보를 넣고)에서 `python manage.py createsuperuser`.
6. 프론트엔드(Vercel) 프로젝트의 환경변수 `VITE_API_BASE_URL`을 이 주소로 설정하고 다시 배포한다.

`.env`는 git에 없으므로 Render 이미지에는 들어가지 않는다. 설정은 모두 Render 환경변수로 한다.
`main`에 푸시하면 Render가 자동으로 다시 배포한다.

## 기존 NestJS 서버에서 전환하기

### 0. 전환 전 점검 (기존 DB에서 실행)

레시피가 깨진 물품이 있어도 전환 후 시세 수정(PUT /market)이나 다른 쓰기는 막히지 않는다. 다만 그 물품과,
그 물품을 하위 물품으로 쓰는 물품은 결과를 다시 계산할 수 없다. 이미 저장된 결과는 지우지 않으므로 마지막 값 그대로
결과 목록(GET /result)에 남고(낡은 가격이라는 표시는 없다), 계산기(POST /result/calculator)에서만 빠진다.
결과가 없던 물품은 결과 목록에도 나오지 않는다. 아래 쿼리로 미리 찾아 두고,
전환 뒤에는 관리자로 `GET /catalog/check`(관리 화면 '데이터 점검')를 열어 남은 문제를 확인한다.

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
   이 명령은 모든 결과를 현재 시세로 다시 계산하고, 결과가 없는 물품의 결과를 만든다.
   엄격 모드라서 계산할 수 없는 물품이 하나라도 있으면 아무것도 저장하지 않고 원인을 모두 알려 준다.
   레시피를 바로 고칠 수 없으면 관리 화면 '데이터 점검 → 결과 다시 맞추기'(`POST /result`)를 누른다.
   계산할 수 있는 결과는 모두 맞추고, 남은 문제는 '데이터 점검'에 보인다. 하위 물품부터 고친다.

### 롤백

기존 DB에서 전환한 경우에만 Nest 서버로 되돌릴 수 있다 (Django는 기존 테이블 구조를 바꾸지 않는다).
Django `migrate`로 새로 만든 DB에는 Nest(`synchronize: true`)를 붙이지 않는다. 붙이면 Nest가 Django의 FK와 인덱스를 지우고 다시 만든다.

## 회원과 권한

- 누구나 회원가입(`POST /auth/signup`)하고 로그인할 수 있다. 조회·계산 API는 로그인 없이 쓴다.
- 쓰기 API(아래 표의 **관리자**)는 관리자(`is_staff`) 계정만 쓴다. 로그인하지 않았으면 401, 일반 회원이면 403이다.
- 이미 배포된 서버에 이 기능을 올릴 때: `main`에 머지하면 Render가 바로 배포해서, 토큰을 보내지 않는 기존 프론트의
  관리 기능(로그인·쓰기)이 멈춘다. 프론트의 `/auth/login`·Bearer 토큰 지원을 먼저 준비한 뒤 백엔드를 머지하고,
  `createsuperuser`로 관리자를 만든 다음 프론트를 배포한다.
- 회원가입할 때 게임 닉네임(`nickname`, 20자 이하, 앞뒤 공백 제거)을 꼭 받는다. 다른 회원과 같아도 된다.
  `createsuperuser`로 만든 관리자의 닉네임은 `관리자`다. 닉네임 추가 전에 있던 회원은 마이그레이션이 채운다
  (관리자 `관리자`, 일반 회원은 아이디 앞 20자).
- 회원은 기초 재료(시세가 있는 최하위 재료)를 몇 개 가졌는지 저장할 수 있다(`/inventory`). 본인 것만 읽고 쓴다.
  시세를 id로 가리켜서 시세 이름을 바꾸면 따라가고, 시세나 회원이 지워지면 함께 지워진다.
  프론트는 결과·장바구니 합산·자유 모드 결과에서 필요 개수에서 보유 개수를 뺀 부족 개수를 함께 보여 준다.
- 시세마다 얻는 곳 분류(`group`: 작물·광물·별빛 재료 등, `apps/markets/models.py`의 `MarketGroup`)가 있다.
  프론트가 재료를 묶어 보여 주는 데만 쓰고 계산에는 쓰지 않는다. 분류를 보내지 않은 새 시세는 기타(`ETC`)이고,
  관리자가 시세 관리 화면에서 고친다. 분류를 추가하거나 이름을 바꾸려면 백엔드와 프론트의 목록을 함께 고친다.
- 관리자는 `python manage.py createsuperuser`로 만든다. 이미 가입한 회원을 관리자로 바꾸려면
  `python manage.py shell -c "from apps.accounts.models import User; User.objects.filter(username='<아이디>').update(is_staff=True)"`.
- 로그인·가입 응답의 `token`을 이후 요청 헤더에 `Authorization: Bearer <token>`으로 넣는다.
  토큰은 7일 동안 유효하고(`expiresAt`), 로그인(기기)마다 따로 발급된다. DB에는 토큰의 SHA-256 해시만 저장한다.
- 토큰이 틀리거나 만료됐으면 익명으로 처리한다. 공개 API는 그대로 응답하고, 로그인이 필요한 API는 401이다.
- 로그아웃은 그 기기의 토큰만 지운다. 비밀번호를 바꾸면 모든 기기의 토큰을 지우고 새 토큰을 준다.
- 비밀번호는 Django 기본 검사(8자 이상, 흔한 비밀번호·숫자만·아이디와 비슷한 비밀번호 금지)를 통과해야 한다.
  아이디는 대소문자만 다른 아이디를 따로 만들 수 없다 (`Admin`이 있으면 `admin` 가입 불가). 로그인할 때는 대소문자를 구분한다.
  아이디는 NFKC로 바꿔 저장하고 비교한다 (전각 `ａｂｃ` → `abc`).
- 로그인·가입·비밀번호 확인(변경·탈퇴)은 횟수를 제한한다 (로그인·비밀번호 확인 분당 10회, 가입 시간당 10회, 넘으면 429).
  제한 기록은 프로세스 메모리에 있어서 gunicorn worker마다 따로 세고, 재시작하면 지워진다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 헬스 체크 (`Hello World!`) |
| POST | `/auth/signup` | `{username, password, nickname}` 회원가입 후 로그인 `{token, expiresAt, user}` (201) |
| POST | `/auth/login` | `{username, password}` 로그인 `{token, expiresAt, user: {id, username, nickname, isAdmin}}` |
| POST | `/auth/logout` | 이 기기의 토큰 삭제 (204, 토큰이 없어도 204) |
| GET | `/auth/me` | 내 정보 `{id, username, nickname, isAdmin}` (로그인) |
| PATCH | `/auth/me` | `{nickname}` 닉네임 변경, 바뀐 내 정보 (아이디는 바꿀 수 없음, 로그인) |
| PUT | `/auth/password` | `{currentPassword, newPassword}` 비밀번호 변경, 새 `{token, expiresAt, user}` (로그인) |
| DELETE | `/auth/me` | `{password}` 회원 탈퇴 (204, 로그인) |
| GET | `/inventory` | 내 보유 재료 `[{marketId, name, count}]` (시세 id 순, 개수가 0인 재료는 없음) (로그인) |
| PUT | `/inventory` | `[{marketId, count}]` 보낸 시세의 보유 개수만 저장(0이면 삭제), 저장 뒤 전체 보유 재료. 없는 시세·중복 시세는 400 (로그인) |
| GET | `/product?page&size&name` | 물품 목록 (재료 포함) `{totalElements, content}` |
| POST | `/product` | 물품 추가 (재료 포함), 결과도 생성 (관리자) |
| POST | `/product/all` | `{products: [...]}` 일괄 추가 (이미 있는 물품은 건너뜀), 새 물품 전부의 결과도 생성 (관리자) |
| PUT | `/product` | 물품 수정 (보낸 필드만 수정, 재료는 통째로 교체), 이 물품과 상위 물품의 결과도 갱신 (관리자) |
| DELETE | `/product` | `{ids: [...]}` 또는 `[id, ...]` 삭제 (재료·결과도 함께 삭제) (관리자) |
| GET | `/market` | 시세 목록 `[{id, name, price, group}]` |
| PUT | `/market` | `[{id?, name?, price?, group?}]` 시세 수정/추가(새 시세의 group은 없으면 `ETC`) 후 전체 결과 동기화. 이름을 바꾸면 그 이름을 쓰는 기본 재료도 바뀌고, 새 시세로 계산할 수 있게 된 물품의 결과도 생성. 모르는 id는 400 (관리자) |
| DELETE | `/market` | `{ids: [...]}` 또는 `[id, ...]` 삭제, `{deletedIds}` (재료로 쓰이는 시세는 400, 없는 id는 무시) (관리자) |
| POST | `/result` | 전체 동기화 (빠진 결과 생성 + 낡은 결과 제자리 갱신, 계산할 수 없는 물품은 건너뜀). 항상 201, 새로 만든 결과 행만 응답 (관리자) |
| GET | `/result?page&size&name&count&tool&category` | 결과 목록 (`count`개 제작 기준) |
| POST | `/result/calculator` | `{markets: [{name, price}]}` 입력 시세로 미리 계산 (저장 안 함, price가 null이면 0원). 결과가 없거나 서버 데이터 문제로 계산할 수 없는 물품은 건너뛰고, 입력에서 DB 시세를 뺀 경우만 400 |
| GET | `/catalog/check` | 데이터 점검 `{summary, products, markets, problems}` (저장 안 함) (관리자) |
| GET | `/experience` | 레벨별 경험치 |
| GET | `/experience/walnut?presentLevel&presentExperience&objectiveLevel&productionPercent` | 호두나무 수확 횟수와 식물앰플 비용 |

요청 본문은 JSON만 받는다. 에러 응답은 NestJS와 같은 형식이다: `{"statusCode": 400, "message": "...", "error": "Bad Request"}`

## 계산 로직 (`apps/results/calculator.py`)

물품 레시피를 기본 재료(시세로 사는 재료)까지 펼쳐서 재료별 총 수량과 가격을 구한다.

- 물품/시세를 이름으로 바로 찾는다 (dict). 기존에는 큐에서 꺼낼 때마다 전체 물품 목록을 훑었다.
- 물품마다 펼친 결과를 한 번만 계산해 메모해 두고 재사용한다. 전체 결과 생성·재계산도 물품 수에 비례하는 시간에 끝난다.
- 재료 순서는 기존 BFS와 같다 (얕은 단계 먼저, 같은 단계는 레시피 순서). 물품마다 '단계별 수량'을 메모해서 순서를 맞춘다.
- 입력 데이터를 바꾸지 않는다. 기존에는 재료 객체의 수량을 직접 더해서 같은 요청에서 뒤에 계산되는 물품의 수량이 틀어졌다.
- 잘못된 하위 재료명, 순환 참조, 시세 없는 재료는 무한 루프나 잘못된 저장 대신 에러(RecipeError)로 알린다.
  계산기는 첫 오류에서 멈추므로, 저장 전 검사와 데이터 점검은 모든 문제를 한 번에 찾는 `diagnosis.py`가 맡는다.
- 레시피에 같은 기본 재료가 여러 줄 있으면 한 줄로 합친다 (기존에는 최상위 레시피에서만 줄이 나뉘었다).

## 기존 대비 달라진 동작

로그인(`/product/login` 대신 `/auth/login`)과 쓰기 API의 관리자 토큰을 빼면, 프론트엔드(my-home-frontend)가 쓰는
정상 요청의 응답 형식은 그대로다. 응답에 키가 추가된 곳만 있다
(결과 항목의 최상위 `category`, 물품 추가·수정 응답의 `id`/`materials`, 시세 응답의 `group`).
새 엔드포인트(`DELETE /market`, `GET /catalog/check`)만 새 응답 모양을 쓴다. 에러 응답 형식은 바뀌지 않는다.

**시세·물품·결과 연결** (`apps/results/sync.py`)
- 물품 추가·일괄 추가·수정·삭제, 시세 수정·삭제가 성공하면 같은 트랜잭션 안에서 결과도 맞춰진다. 계산할 수 있는 모든 물품에
  결과가 하나씩 있고, 그 값은 현재 레시피 × 현재 DB 시세와 같다. '결과 리스트 생성'(POST /result)을 따로 부르지 않아도 된다.
- 결과는 지우고 다시 만들지 않고 제자리에서 고친다. 결과 id와 createdAt은 물품이 있는 동안 그대로이고,
  updatedAt은 값이 실제로 바뀐 행만 바뀐다 (같은 값을 다시 저장하면 결과 UPDATE가 나가지 않는다).
- 쓰기가 차단 문제를 **새로** 만들면 400이고 전부 취소된다. 차단 문제는 없는 하위 물품, 시세 없는 기본 재료, 순환 참조,
  합계가 정수 컬럼 범위(약 21억)를 넘는 것, 계산할 수 없는 하위 물품을 쓰는 것이다.
  메시지 하나에 모든 문제를 묶어 알린다 (예: `시세 정보가 없는 재료가 있습니다. (새물품: 은, 새물품: 금)`). 문제가 1건이면 기존 문구와 같다.
- 시세 없는 기본 재료를 쓰는 물품은 이제 저장할 수 없다. 새 재료라면 PUT /market으로 시세를 먼저 추가하고 물품을 저장한다.
- 이미 있던 문제(기존 데이터, DB 직접 수정)는 다른 쓰기를 막지 않는다. 그런 물품의 저장된 결과는 지우지 않고 마지막 값으로 두고,
  데이터 점검(GET /catalog/check)에 보인다. 문제가 있는 물품도 새 문제를 만들지 않으면 수정할 수 있다.
- 레시피는 물품·시세를 이름으로 가리키므로 이름 변경을 따라간다. 물품 이름을 바꾸면 하위 물품 재료(basic=False)가,
  시세 이름을 바꾸면 기본 재료(basic=True)가 함께 바뀐다. 다른 레시피가 쓰는 물품이나 시세는 삭제할 수 없다.
- 모든 카탈로그 쓰기(와 POST /result, 관리 명령)는 시세 행 전체를 id 순으로 잠그는 같은 전역 잠금을 가장 먼저 잡아 차례로 실행된다.
  시세 테이블이 비어 있으면 잠글 행이 없다 (운영 시세는 비지 않으므로 다루지 않는다).

**계산·저장**
- 결과는 DB의 **전체 시세**로 계산하고 names/counts/prices/totalPrice를 모두 갱신한다.
- 결과 생성(POST /result)은 전체 동기화이고 항상 201이다. 빠진 결과를 만들고 낡은 결과를 고치며, 계산할 수 없는 물품은 건너뛴다.
  응답은 이번에 새로 만든 결과 행만이다 (없으면 `[]`). 기존 '추가할 결과가 없습니다.' 400은 없다.
- 시세 수정(PUT /market)에 없는 id를 보내면 새 행을 만들지 않고 400이다 (`존재하지 않는 시세입니다. (id: 999)`).
- 계산기(POST /result/calculator) 응답의 `id`는 결과 id다 (기존에는 물품 id로 덮어썼다). 결과는 레벨, 이름 순으로 정렬된다.
  결과가 없는 물품과 서버 데이터 문제로 계산할 수 없는 물품은 목록에서 빠진다 (기존에는 하나만 있어도 모두에게 400).
  입력에서 DB에 있는 시세를 뺀 경우만 400이다.
- 결과 응답의 `totalPrice`는 재료 가격의 합이다. totalPrice 컬럼(정수)에는 반올림(.5 올림)해 저장한다. 기존에는 합계가 소수면 저장하다 500이 났다.
  저장할 합계가 정수 컬럼 범위(약 21억)를 넘는 물품은 결과를 저장하지 않는다 (쓰기가 새로 만들면 400). 저장하지 않는 계산기에는 이 제한이 없다.
- 응답 숫자의 부동소수점 오차를 정리한다 (예: `0.30000000000000004` → `0.3`). 재료가 없는 물품의 결과 materials는 `[]`다.

**물품**
- 물품 추가·수정 시 레시피를 검증한다. 존재하지 않는 하위 물품, 시세 없는 기본 재료, 순환 참조가 새로 생기면 400이다 (일괄 추가는 같은 업로드 안의 물품을 참조해도 된다).
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
- 쓰기 API는 관리자 계정으로 로그인해야 쓸 수 있다 (기존에는 누구나 호출할 수 있었다). 공용 비밀번호 로그인(`POST /product/login`)과
  `PASSWORD` 환경변수는 없어졌다. 회원·권한은 위 '회원과 권한'을 본다.
- 요청 본문 50MB 제한이 실제로 적용된다 (413). 폼(urlencoded) 본문은 받지 않는다 (415).
- 지원하지 않는 HTTP 메서드는 404 대신 405다.
