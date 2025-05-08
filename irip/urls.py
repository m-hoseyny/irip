"""
URL configuration for irip project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

# Swagger/OpenAPI schema configuration
schema_view = get_schema_view(
    openapi.Info(
        title="IRIP API",
        default_version='v1',
        description="API for VPN account management with JWT authentication.\n\n"
                    "**Authentication:**\n"
                    "1. First, obtain a token at `/api/v1/user/token/`\n"
                    "2. Click the 'Authorize' button at the top right\n"
                    "3. In the 'Value' field, enter: `Bearer your_token_here`\n"
                    "4. Click 'Authorize' and close the dialog\n"
                    "5. Now you can use the authenticated endpoints",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    authentication_classes=(SessionAuthentication, JWTAuthentication),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API endpoints
    path('api/v1/user/', include('user.urls')),
    # path('api/v1/subscription/', include('subscription.urls')),
    # path('api/v1/vpn-account/', include('vpn_account.urls')),
    # path('api/v1/file-management/', include('file_management.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

