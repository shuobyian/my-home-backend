import pytest
from django.core.validators import MinLengthValidator
from rest_framework.exceptions import ValidationError

from apps.common.fields import CsvSafeNameField


def test_csv_safe_name_field_keeps_comma_check_first_with_extra_validators():
    extra = [MinLengthValidator(5)]  # "a,b"(3자)는 이 validator에도 걸린다
    field = CsvSafeNameField(validators=extra)

    with pytest.raises(ValidationError) as error:
        field.run_validation("a,b")

    # 최소 길이 문구는 Django 번역에 묶이므로 code로 순서만 본다.
    assert [detail.code for detail in error.value.detail] == ["invalid", "min_length"]
    assert error.value.detail[0] == "이름에 콤마(,)를 넣을 수 없습니다."
    assert len(extra) == 1  # 넘긴 리스트는 바꾸지 않는다


def test_csv_safe_name_field_reports_comma_before_length():
    with pytest.raises(ValidationError) as error:
        CsvSafeNameField().run_validation("a,b" + "x" * 300)

    assert error.value.detail[0] == "이름에 콤마(,)를 넣을 수 없습니다."
    assert len(error.value.detail) == 2
