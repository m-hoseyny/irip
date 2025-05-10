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
from drf_yasg.generators import OpenAPISchemaGenerator
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

# Swagger/OpenAPI schema configuration
# Custom schema generator that handles file uploads better
class CustomSchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request, public)
        # Add security requirement for all endpoints
        if schema.security_definitions and 'Bearer' in schema.security_definitions:
            schema.security = [{'Bearer': []}]
        return schema

schema_view = get_schema_view(
    openapi.Info(
        title="IRIP API",
        default_version='v1',
        description="""API for IRIP VPN Account Management System.

## Authentication

This API uses JWT Authentication. To authenticate:

1. Use the `/api/v1/user/token/` endpoint to obtain a token
2. Click the 'Authorize' button at the top of this page
3. Enter your token in the format: `Bearer <your_token>`
4. Click 'Authorize' and close the popup

You should now be able to use all authenticated endpoints.

## File Uploads

For endpoints that require file uploads (like verification photos):

1. Make sure you're authenticated (see above)
2. Use the 'Try it out' button on the endpoint
3. Use the file selector to choose your file
4. Click 'Execute' to upload

The file will be uploaded as multipart/form-data automatically.
""",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="Example License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    authentication_classes=(JWTAuthentication,),
    generator_class=CustomSchemaGenerator,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API endpoints
    path('api/v1/user/', include('user.urls')),
    path('api/v1/subscription/', include('subscription.urls')),
    # path('api/v1/vpn-account/', include('vpn_account.urls')),
    path('api/v1/file-management/', include('file_management.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

