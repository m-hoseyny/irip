from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from .views import UserViewSet, verify_email

router = DefaultRouter()
router.register(r'', UserViewSet)

urlpatterns = [
    # JWT Authentication endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Email verification endpoint
    path('verify-email/<str:uidb64>/<str:token>/', verify_email, name='verify_email'),
    
    # User API endpoints
    path('', include(router.urls)),
]
