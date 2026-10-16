from dataclasses import dataclass

from apps.common.exceptions import BadRequest
from apps.experiences.models import Experience
from apps.results.models import Result

WALNUT_MIN_LEVEL = 55
MAX_LEVEL = 112
WALNUT_EXPERIENCE = 65340
AMPLE_PRODUCT_NAME = "식물앰플-중급 가속"


@dataclass(frozen=True, slots=True)
class WalnutPlan:
    remind_experience: int
    remind_count: int
    ample: Result


def list_experiences():
    return Experience.objects.order_by("level")


def calculate_walnut(present_level, present_experience, objective_level, production_percent):
    """목표 레벨까지 필요한 호두나무 수확 횟수와, 그만큼 필요한 식물앰플 결과를 구한다.

    목표 레벨에 도달하려면 현재 레벨부터 (목표 레벨 - 1)까지의 경험치를 채워야 한다.
    """
    if present_level < WALNUT_MIN_LEVEL:
        raise BadRequest(f"호두나무는 {WALNUT_MIN_LEVEL}렙 이상부터 생산 가능합니다. 레벨업하고 오세요.")
    if objective_level is None:
        objective_level = present_level + 1
    if objective_level > MAX_LEVEL:
        raise BadRequest(f"Lv.{MAX_LEVEL}이 만렙입니다.")
    if objective_level <= present_level:
        raise BadRequest("목표 레벨은 현재 레벨보다 높아야 합니다.")

    levels = range(present_level, objective_level)
    # 레벨마다 쿼리하던 기존 방식 대신 필요한 레벨을 한 번에 조회한다.
    amounts = dict(Experience.objects.filter(level__in=levels).values_list("level", "amount"))
    missing = [str(level) for level in levels if level not in amounts]
    if missing:
        raise BadRequest(f"경험치 정보가 없는 레벨이 있습니다. (Lv.{', '.join(missing)})")
    if amounts[present_level] <= present_experience:
        raise BadRequest("입력한 경험치가 현재 레벨 경험치보다 많습니다. 다시 설정해 주세요.")

    remind_experience = sum(amounts.values()) - present_experience
    walnut_experience = int(WALNUT_EXPERIENCE * (1 + production_percent / 100))
    remind_count = int(remind_experience / walnut_experience)

    ample = Result.objects.with_product().filter(product__name=AMPLE_PRODUCT_NAME).first()
    if ample is None:
        raise BadRequest(f"{AMPLE_PRODUCT_NAME} 결과 정보가 없습니다.")

    return WalnutPlan(remind_experience, remind_count, ample)
