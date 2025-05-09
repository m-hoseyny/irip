from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VerificationPhotoViewSet

router = DefaultRouter()
router.register(r'verification-photos', VerificationPhotoViewSet, basename='verification-photos')

urlpatterns = [
    path('', include(router.urls)),
]
