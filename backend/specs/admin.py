from django.contrib import admin

from .models import Spec, SpecRevision


@admin.register(Spec)
class SpecAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "status", "created_at", "updated_at")
    list_filter = ("status", "owner")
    search_fields = ("requirement", "owner__username", "owner__email")
    autocomplete_fields = ("owner",)


@admin.register(SpecRevision)
class SpecRevisionAdmin(admin.ModelAdmin):
    list_display = ("id", "spec", "note", "created_at")
