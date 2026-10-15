import uuid

from django.conf import settings
from django.db import models


class Spec(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        REVIEWED = "reviewed", "已确认"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="specs",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    requirement = models.TextField()
    result = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.result.get("title", "未命名需求")[:80]


class SpecRevision(models.Model):
    spec = models.ForeignKey(Spec, related_name="revisions", on_delete=models.CASCADE)
    result = models.JSONField()
    note = models.CharField(max_length=240, default="人工审阅修改")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
