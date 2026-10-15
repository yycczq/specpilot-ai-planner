# Generated for the SpecPilot portfolio prototype.
import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Spec",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("requirement", models.TextField()),
                ("result", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[("draft", "草稿"), ("reviewed", "已确认")], default="draft", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="SpecRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("result", models.JSONField()),
                ("note", models.CharField(default="人工审阅修改", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("spec", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="specs.spec")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
