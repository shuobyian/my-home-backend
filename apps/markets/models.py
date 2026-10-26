from django.db import models


# 기초 재료를 얻는 곳으로 나눈 분류. 화면에서 묶어 보여 주는 데만 쓰고 계산에는 쓰지 않는다.
# 보여 주는 순서대로 적고, 값과 이름은 프론트엔드(my-home-frontend src/types/enums.ts)의 목록과 같아야 한다.
class MarketGroup(models.TextChoices):
    CROP = "CROP", "작물"
    TREE_FRUIT = "TREE_FRUIT", "나무 열매"
    TIMBER = "TIMBER", "목재"
    LIVESTOCK = "LIVESTOCK", "축산"
    ROBIN_SHOP = "ROBIN_SHOP", "로빈샵"
    SEAFOOD = "SEAFOOD", "수산물"
    SEA_GATHERING = "SEA_GATHERING", "바다 채집"
    MINERAL = "MINERAL", "광물"
    GEM = "GEM", "보석"
    BUSH_GATHERING = "BUSH_GATHERING", "수풀 채집"
    STAR_FRUIT = "STAR_FRUIT", "별 열매"
    STARLIGHT = "STARLIGHT", "별빛 재료"
    BADGE = "BADGE", "뱃지"
    EVENT = "EVENT", "이벤트"
    ETC = "ETC", "기타"


class MarketQuerySet(models.QuerySet):
    def lock_all(self):
        """시세 행 전체를 id 순서로 잠근다. 트랜잭션 안에서만 쓴다. 항상 같은 순서로 잠가 교착을 피한다."""
        return self.select_for_update().order_by("id")


class Market(models.Model):
    """기본 재료의 시세."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    price = models.IntegerField()
    group = models.CharField(max_length=255, choices=MarketGroup.choices, default=MarketGroup.ETC)

    objects = MarketQuerySet.as_manager()

    class Meta:
        db_table = "market"

    def __str__(self):
        return f"{self.name} ({self.price})"
