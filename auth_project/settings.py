"""
Django settings for auth_project project.
"""

from datetime import timedelta
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-*=0!4ijz6v1t5xsl5pgp5zy!c4fl(%x5o5)l+m%9g0+7!$)u*p'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']  # ✅ un seul, plus sécurisé que '*'


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'accounts',
    'localisations',
    'pharmacies.apps.PharmaciesConfig',
    #'auth_project',
    'rest_framework_simplejwt.token_blacklist',
    'django_crontab',
    'stock',
    'reservations',
    'urgences',
]

CRONJOBS = [
    ('1 0 1 * *', 'django.core.management.call_command', ['generer_gardes']),
    ('0 1 1 * *', 'django.core.management.call_command', ['generer_horaires_ramadan']),
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # ✅ doit être en premier
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'auth_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'auth_project.wsgi.application'

# Email Configuration
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = 'chaimakharoubi73@gmail.com'
EMAIL_HOST_PASSWORD = 'pwkt vxrj yoaj ubno'
DEFAULT_FROM_EMAIL  = 'chaimakharoubi73@gmail.com'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'authentification'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'chaima123'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5433'),
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True

# Static files
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Modèle utilisateur personnalisé
AUTH_USER_MODEL = 'accounts.User'

# ─── DRF ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.CustomJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",   # ✅ ajouté
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",   # ✅ ajouté
]


# Twilio SMS
TWILIO_ACCOUNT_SID = 'AC2c04d13813aac77234eb22b2463687c8'
TWILIO_AUTH_TOKEN  = 'c25e35b14462c2385f0aaad415fcb7b3'
TWILIO_FROM_NUMBER = '+16624282878'   


CORS_ALLOW_CREDENTIALS = True  # ✅ indispensable pour les cookies

# ─── Cookies de session ───────────────────────────────────────────────────────
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE    = 'Lax'

# ─── JWT ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME'  : timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME' : timedelta(days=1),
    'AUTH_HEADER_TYPES'      : ('Bearer',),
    'AUTH_COOKIE'            : 'access_token',
    'AUTH_COOKIE_REFRESH'    : 'refresh_token',
    'AUTH_COOKIE_HTTPONLY'   : True,
    'AUTH_COOKIE_SAMESITE'   : 'Lax',
    'AUTH_COOKIE_SECURE'     : False,  # dev only — mettre True en production
}