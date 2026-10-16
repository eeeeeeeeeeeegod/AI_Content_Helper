import os

import pytest


# ============================================
# 測試環境變數
# 必須放在 import app 之前
# ============================================

os.environ["APP_ENV"] = "development"

os.environ["FLASK_SECRET_KEY"] = (
    "test-secret-key"
)

os.environ["OPENAI_API_KEY"] = (
    "test-openai-key"
)

# 使用獨立的記憶體資料庫
os.environ["DATABASE_URL"] = (
    "sqlite:///:memory:"
)

# 測試時不用 Redis
os.environ["REDIS_URL"] = ""

# 測試時不用真的連 R2
os.environ["R2_ACCOUNT_ID"] = ""
os.environ["R2_ACCESS_KEY_ID"] = ""
os.environ["R2_SECRET_ACCESS_KEY"] = ""
os.environ["R2_BUCKET_NAME"] = ""


# ============================================
# 環境設定完成後才 import
# ============================================

from app import app
from extensions import db


@pytest.fixture()
def test_app():

    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False
    )

    with app.app_context():

        db.create_all()

        yield app

        db.session.remove()

        db.drop_all()


@pytest.fixture()
def client(test_app):

    with test_app.test_client() as client:

        yield client