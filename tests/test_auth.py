from werkzeug.security import (
    generate_password_hash
)

from extensions import db
from models import User


def create_test_user():

    user = User(
        email="test@example.com",
        password_hash=generate_password_hash(
            "123456789012"
        )
    )

    db.session.add(
        user
    )

    db.session.commit()

    return user

def test_register_success(client):

    response = client.post(
        "/register",
        data={
            "email":
                "newuser@example.com",

            "password":
                "123456789012",

            "confirm_password":
                "123456789012"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    user = User.query.filter_by(
        email="newuser@example.com"
    ).first()

    assert user is not None

    assert (
        "newuser@example.com"
        .encode("utf-8")
        in response.data
    )
    
def test_login_success(client):

    create_test_user()

    response = client.post(
        "/login",
        data={
            "email":
                "test@example.com",

            "password":
                "123456789012"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert (
        "test@example.com"
        .encode("utf-8")
        in response.data
    )
    
def test_login_wrong_password(client):

    create_test_user()

    response = client.post(
        "/login",
        data={
            "email":
                "test@example.com",

            "password":
                "wrong-password"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert (
        "Email 或密碼錯誤"
        .encode("utf-8")
        in response.data
    )
    
def test_logout(client):

    create_test_user()

    # 登入
    client.post(
        "/login",
        data={
            "email":
                "test@example.com",

            "password":
                "123456789012"
        }
    )

    # 登出
    response = client.post(
        "/logout",
        follow_redirects=False
    )

    assert response.status_code == 302

    # 登出後再次進 history
    response = client.get(
        "/history",
        follow_redirects=False
    )

    assert response.status_code == 302

    assert (
        "/login"
        in response.headers["Location"]
    )