import os
import socket
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dcg4gxd_tlcau9wbxn0yy@lg$5vm##utbx=@qiz9pn1785-%aj",
)

DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

def _default_allowed_hosts() -> list[str]:
    hosts = ["localhost", "127.0.0.1", "10.0.2.2"]
    if DEBUG:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                hosts.append(sock.getsockname()[0])
        except OSError:
            pass
    return hosts


_hosts_from_env = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]
ALLOWED_HOSTS = list(
    dict.fromkeys(
        (_hosts_from_env or _default_allowed_hosts())
        + (_default_allowed_hosts() if DEBUG else [])
    )
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'accounts',
    'library',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'ninja.compatibility.files.fix_request_files_middleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'


def _database_url_implies_ssl_require(database_url: str) -> bool:
    parsed = urlparse(database_url)
    query = parse_qs(parsed.query, keep_blank_values=False)
    for mode in query.get("sslmode", []):
        if str(mode).lower() in {"require", "verify-ca", "verify-full"}:
            return True
    for flag in query.get("ssl", []):
        if str(flag).lower() in {"1", "true", "yes", "on"}:
            return True
    return False


_database_url = os.getenv("DATABASE_URL")
if not _database_url:
    raise ImproperlyConfigured("Defina DATABASE_URL com uma conexão PostgreSQL.")

DATABASES = {
    "default": dj_database_url.config(
        conn_max_age=600,
        ssl_require=_database_url_implies_ssl_require(_database_url),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

AUTH_USER_MODEL = "accounts.User"

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8081,http://127.0.0.1:8081,exp://127.0.0.1:8081",
    ).split(",")
    if o.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
