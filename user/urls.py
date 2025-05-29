from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from .views import (UserViewSet, verify_email, password_reset_request, password_reset_confirm,
                  google_login, oauth_complete, oauth_error)

router = DefaultRouter()
router.register(r'', UserViewSet)

urlpatterns = [
    # JWT Authentication endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Email verification endpoint
    path('verify-email/<str:uidb64>/<str:token>/', verify_email, name='verify_email'),
    
    # Password reset endpoints
    path('reset-password/', password_reset_request, name='password_reset_request'),
    path('reset-password-confirm/<str:uidb64>/<str:token>/', password_reset_confirm, name='password_reset_confirm'),
    
    # OAuth endpoints
    path('oauth/google/', google_login, name='google_login'),
    path('oauth/complete/', oauth_complete, name='oauth_complete'),
    path('oauth/error/', oauth_error, name='oauth_error'),
    
    # User API endpoints
    path('', include(router.urls)),
]
