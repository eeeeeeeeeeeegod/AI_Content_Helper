from flask import (
    request,
    current_app
)

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def get_client_ip():

    if current_app.config.get(
        "IS_PRODUCTION",
        False
    ):

        forwarded_for = request.headers.get(
            "X-Forwarded-For",
            ""
        )

        if forwarded_for:

            return (
                forwarded_for
                .split(",")[0]
                .strip()
            )

    return (
        request.remote_addr
        or "unknown"
    )


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[]
)