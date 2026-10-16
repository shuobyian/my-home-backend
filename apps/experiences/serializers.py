from rest_framework import serializers

from apps.experiences.models import Experience


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ["id", "level", "amount"]
