"""Narrow REST read surface for Rene's renewal-book credential."""

from rest_framework.response import Response
from rest_framework.views import APIView

from crm_app.rene_auth import (
    IsExactReneRenewalReader,
    ReneRenewalBearerAuthentication,
    capability_receipt,
)


class _ExactReneReadView(APIView):
    authentication_classes = [ReneRenewalBearerAuthentication]
    permission_classes = [IsExactReneRenewalReader]


class ReneTokenCapabilitiesView(_ExactReneReadView):
    def get(self, request):
        return Response(capability_receipt(request.user))
