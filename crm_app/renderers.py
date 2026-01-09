"""
Custom renderers for handling UUID serialization
"""
import json
import uuid
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.renderers import JSONRenderer


class UUIDJSONEncoder(DjangoJSONEncoder):
    """
    JSON encoder that properly handles UUID objects by converting them to strings.
    Extends DjangoJSONEncoder which already handles datetime, Decimal, etc.
    """
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


class UUIDJSONRenderer(JSONRenderer):
    """
    Custom JSON renderer that uses UUIDJSONEncoder to handle UUID serialization.
    """
    encoder_class = UUIDJSONEncoder
