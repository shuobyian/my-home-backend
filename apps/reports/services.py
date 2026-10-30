from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.logs.models import Action
from apps.logs.services import record
from apps.reports.models import Report, ReportChange, ReportStatus


def list_reports(*, status=None, kind=None):
    reports = Report.objects.select_related("author").prefetch_related("changes").order_by("-id")
    if status:
        reports = reports.filter(status=status)
    if kind:
        reports = reports.filter(kind=kind)
    return reports


def get_report(pk):
    report = list_reports().filter(pk=pk).first()
    if report is None:
        raise NotFound("존재하지 않는 제보입니다.")
    return report


def _lock(pk):
    # 쓴 사람의 수정과 관리자의 처리가 겹치지 않도록 잠근다. (외부 조인과 함께 잠글 수 없어 따로 읽는다)
    report = Report.objects.select_for_update().filter(pk=pk).first()
    if report is None:
        raise NotFound("존재하지 않는 제보입니다.")
    return report


def _check_author(report, user):
    if report.author_id != user.pk:
        raise PermissionDenied("내가 쓴 제보만 고치거나 지울 수 있습니다.")
    if report.status != ReportStatus.OPEN:
        raise PermissionDenied("처리된 제보는 고치거나 지울 수 없습니다.")


def _save_changes(report, changes):
    report.changes.all().delete()
    ReportChange.objects.bulk_create(ReportChange(report=report, **change) for change in changes)


@transaction.atomic
def create_report(request, data):
    changes = data.pop("changes")
    report = Report.objects.create(author=request.user, **data)
    _save_changes(report, changes)
    record(request, Action.REPORT_CREATE, report_id=report.pk, detail={"title": report.title})
    return get_report(report.pk)


@transaction.atomic
def update_report(request, pk, data):
    """쓴 사람이 접수 상태의 제보를 고친다. 바꿀 값은 통째로 바꾼다."""
    report = _lock(pk)
    _check_author(report, request.user)
    changes = data.pop("changes")
    for field, value in data.items():
        setattr(report, field, value)
    report.save()
    _save_changes(report, changes)
    record(request, Action.REPORT_UPDATE, report_id=report.pk, detail={"title": report.title})
    return get_report(report.pk)


@transaction.atomic
def answer_report(request, pk, data):
    """관리자가 상태(반영·반려)와 답변을 정한다. 데이터 자체는 관리 화면에서 따로 고친다."""
    report = _lock(pk)
    for field, value in data.items():
        setattr(report, field, value)
    report.save()
    record(
        request,
        Action.REPORT_ANSWER,
        report_id=report.pk,
        detail={"title": report.title, "status": report.status, "answer": report.answer},
    )
    return get_report(report.pk)


@transaction.atomic
def delete_report(request, pk):
    """쓴 사람은 접수 상태일 때, 관리자는 언제든 지울 수 있다."""
    report = _lock(pk)
    if not request.user.is_staff:
        _check_author(report, request.user)
    record(request, Action.REPORT_DELETE, report_id=report.pk, detail={"title": report.title})
    report.delete()
