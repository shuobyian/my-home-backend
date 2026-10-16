"""기존 TypeORM DB에 없는 material.product_id 인덱스를 만든다.

--fake-initial은 테이블이 있으면 초기 마이그레이션을 건너뛰므로, Django가 FK에 만드는 인덱스가 생기지 않는다.
Django가 붙이는 이름과 같은 이름을 쓰므로 새 DB(이미 인덱스가 있음)에서는 아무 일도 하지 않는다.
"""

from django.db import migrations

INDEX_NAME = "material_product_id_f0ba8c31"


def create_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f'CREATE INDEX IF NOT EXISTS "{INDEX_NAME}" ON "material" ("product_id")')


class Migration(migrations.Migration):
    initial = False

    dependencies = [
        ("common", "0001_reset_sequences"),
    ]

    operations = [
        migrations.RunPython(create_index, migrations.RunPython.noop),
    ]
