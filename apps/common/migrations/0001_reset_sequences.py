"""기존 TypeORM DB를 넘겨받을 때 id 시퀀스를 현재 최대 id에 맞춘다.

SQL 등으로 id를 직접 넣은 테이블(예: experience)은 시퀀스가 실제 id보다 뒤처져 있어서,
그대로 두면 Django가 새 행을 넣을 때 id가 겹친다. 새 DB에서는 아무 영향이 없다.
"""

from django.core.management.color import no_style
from django.db import migrations

MODELS = [
    ("products", "Product"),
    ("products", "Material"),
    ("markets", "Market"),
    ("results", "Result"),
    ("experiences", "Experience"),
]


def reset_sequences(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    models = [apps.get_model(app_label, model_name) for app_label, model_name in MODELS]
    with connection.cursor() as cursor:
        for sql in connection.ops.sequence_reset_sql(no_style(), models):
            cursor.execute(sql)


class Migration(migrations.Migration):
    initial = False

    dependencies = [
        ("products", "0001_initial"),
        ("markets", "0001_initial"),
        ("results", "0001_initial"),
        ("experiences", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(reset_sequences, migrations.RunPython.noop),
    ]
