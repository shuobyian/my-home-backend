from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.common.exceptions import BadRequest
from apps.products.models import Product
from apps.results import services
from apps.results.models import Result


class Command(BaseCommand):
    help = "저장된 모든 결과를 현재 시세로 다시 계산한다. 기존 NestJS 서버에서 넘어온 직후 한 번 실행한다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-missing",
            action="store_true",
            help="결과가 없는 물품의 결과도 새로 만든다 (POST /result와 같음).",
        )

    def handle(self, *args, create_missing=False, **options):
        try:
            with transaction.atomic():
                recalculated = Result.objects.count()
                services.recalculate_results()
                created = []
                if create_missing and Product.objects.filter(result__isnull=True).exists():
                    created = services.create_missing_results()
        except BadRequest as error:
            raise CommandError(f"재계산하지 못해 아무것도 저장하지 않았습니다. {error.detail}") from None

        message = f"결과 {recalculated}건을 재계산하고 {len(created)}건을 새로 만들었습니다."
        self.stdout.write(self.style.SUCCESS(message))
