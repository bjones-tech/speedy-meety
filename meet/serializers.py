from rest_framework import serializers


class WebhookSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=200)
    name = serializers.CharField(max_length=200)
    resource = serializers.CharField(max_length=200)
    event = serializers.CharField(max_length=200)
    filter = serializers.CharField(max_length=200)
    data = serializers.DictField()

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass
