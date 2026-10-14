import os

from dotenv import load_dotenv
from flask import Flask


from extensions import (
    db,
    migrate,
    login_manager,
    csrf,
    limiter
)

from models import User

load_dotenv()

# 1. 環境
APP_ENV = os.getenv(
    "APP_ENV",
    "development"
).lower()

IS_PRODUCTION = (
    APP_ENV == "production"
)


# 2. Flask
app = Flask(__name__)

REDIS_URL = os.getenv(
    "REDIS_URL"
)

RATE_LIMIT_STORAGE = (
    REDIS_URL
    if REDIS_URL
    else "memory://"
)


# config
app.config["SECRET_KEY"] = os.getenv(
    "FLASK_SECRET_KEY"
)

if not app.config["SECRET_KEY"]:

    raise RuntimeError(
        "找不到 FLASK_SECRET_KEY，請檢查 .env"
    )
app.config["IS_PRODUCTION"] = IS_PRODUCTION
app.config["RATELIMIT_STORAGE_URI"] = (
    RATE_LIMIT_STORAGE
)
app.config["RATELIMIT_STRATEGY"] = (
    "fixed-window"
)


# 整個 HTTP 請求最大 6 MB
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024



# Database

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if DATABASE_URL:

    # 相容部分雲端平台提供的 postgres:// 格式
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )

    # 使用 psycopg 3
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )

    app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = DATABASE_URL

else:

    # 本機開發繼續使用 SQLite
    app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = "sqlite:///ai_content.db"


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# extensions
db.init_app(app)

migrate.init_app(
    app,
    db,
    render_as_batch=True
)

login_manager.init_app(app)

csrf.init_app(app)

limiter.init_app(app)

login_manager.login_view = "auth.login"

login_manager.login_message = (
    "請先登入後再使用此功能。"
)

from routes.auth import auth_bp
from routes.brands import brands_bp
from routes.projects import projects_bp


app.register_blueprint(auth_bp)
app.register_blueprint(brands_bp)
app.register_blueprint(projects_bp)


# Session 設定

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    IS_PRODUCTION
)



# 載入使用者

@login_manager.user_loader
def load_user(user_id):

    try:

        return db.session.get(
            User,
            int(user_id)
        )

    except (ValueError, TypeError):

        return None


# HTTP Security Headers

@app.after_request
def add_security_headers(response):

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"

    response.headers[
        "X-Frame-Options"
    ] = "SAMEORIGIN"

    response.headers[
        "Referrer-Policy"
    ] = "strict-origin-when-cross-origin"

    if IS_PRODUCTION:

        response.headers[
            "Strict-Transport-Security"
        ] = "max-age=31536000; includeSubDomains"

    return response


@app.errorhandler(413)
def request_entity_too_large(error):

    return (
        "上傳內容過大，請確認文件大小符合限制。",
        413
    )

@app.errorhandler(404)
def page_not_found(error):

    return (
        "找不到此頁面。",
        404
    )

@app.errorhandler(429)
def too_many_requests(error):

    return (
        "請求過於頻繁，請稍後再試。",
        429
    )

@app.errorhandler(500)
def internal_server_error(error):

    try:
        db.session.rollback()

    except Exception:
        pass

    return (
        "伺服器發生錯誤，請稍後再試。",
        500
    )


# Health Check

@app.route("/health")
@limiter.exempt
def health():

    return {
        "status": "ok"
    }, 200



if __name__ == "__main__":

    app.run(
        debug=not IS_PRODUCTION
    )