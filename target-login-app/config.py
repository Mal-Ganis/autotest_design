import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SECRET_KEY = os.environ.get("LOGIN_APP_SECRET", "dev-change-in-production")
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 days
