from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FAQViewSet, TutorialViewSet, TicketViewSet, TicketReplyViewSet

router = DefaultRouter()
router.register(r'faq', FAQViewSet)
router.register(r'tutorial', TutorialViewSet)
router.register(r'ticket', TicketViewSet)
router.register(r'ticket-reply', TicketReplyViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
