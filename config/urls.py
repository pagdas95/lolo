# ruff: noqa
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, re_path
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from dj_rest_auth.registration.views import VerifyEmailView
from dj_rest_auth.views import (
    PasswordResetView,
    PasswordResetConfirmView,
    PasswordChangeView,
)
from dj_rest_auth.registration.views import ResendEmailVerificationView
from lolo.users.api.views import CustomVerifyEmailView

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("lolo.users.urls", namespace="users")),
    path("api/tickets/", include("lolo.tickets.urls", namespace="tickets")),
    path("accounts/", include("allauth.urls")),
    
    # Your stuff: custom urls includes go here
    # ...
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]
if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()

# API URLS
urlpatterns += [


    
    # API base url
    path("api/", include("config.api_router")),
    # DRF auth token
    path("api/auth-token/", obtain_auth_token),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    # dj-rest-auth
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    
    # Email verification URLs
    path(
        'api/auth/verify-email/',
        VerifyEmailView.as_view(),
        name='rest_verify_email'
    ),
    # This endpoint will handle the key in the URL
    re_path(
        r'^api/auth/account-confirm-email/(?P<key>[-:\w]+)/$',
        VerifyEmailView.as_view(),
        name='account_confirm_email'
    ),
        # Explicit password management URLs
    path(
        'api/auth/password/reset/',
        PasswordResetView.as_view(),
        name='rest_password_reset'
    ),
    path(
        'password/reset/confirm/<str:uidb64>/<str:token>/',
        PasswordResetConfirmView.as_view(),
        name='password_reset_confirm'
    ),
    path(
        'api/auth/password/change/',
        PasswordChangeView.as_view(),
        name='rest_password_change'
    ),
    
    
    # Email verification resend
    path(
        'api/auth/registration/resend-email/',
        ResendEmailVerificationView.as_view(),
        name='rest_resend_email'
    ),
    
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
