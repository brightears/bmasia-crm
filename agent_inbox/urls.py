"""Routes under /api/v1/ (included from bmasia_crm/urls.py)."""
from rest_framework.routers import SimpleRouter

from agent_inbox.api import ActivityViewSet, ChangeProposalViewSet

router = SimpleRouter()
router.register(r'activities', ActivityViewSet, basename='inbox-activity')
router.register(r'change-proposals', ChangeProposalViewSet, basename='inbox-change-proposal')

urlpatterns = router.urls
