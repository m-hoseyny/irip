from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VPNAccountViewSet

router = DefaultRouter()
router.register(r'vpn-accounts', VPNAccountViewSet, basename='vpn-account')

urlpatterns = [
    path('', include(router.urls)),
]
