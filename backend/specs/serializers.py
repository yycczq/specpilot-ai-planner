from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Spec, SpecRevision

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined"]
        read_only_fields = fields


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("这个用户名已被使用。")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("这个邮箱已被注册。")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class SpecRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecRevision
        fields = ["id", "result", "note", "created_at"]


class SpecSerializer(serializers.ModelSerializer):
    revision_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Spec
        fields = ["id", "requirement", "result", "status", "created_at", "updated_at", "revision_count"]
        read_only_fields = ["id", "created_at", "updated_at", "revision_count"]
