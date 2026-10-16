from werkzeug.security import (
    generate_password_hash
)

from extensions import db

from models import (
    User,
    Project
)


def create_user(
    email,
    password="123456789012"
):

    user = User(
        email=email,
        password_hash=generate_password_hash(
            password
        )
    )

    db.session.add(
        user
    )

    db.session.commit()

    return user


def login(
    client,
    email,
    password="123456789012"
):

    return client.post(
        "/login",
        data={
            "email": email,
            "password": password
        },
        follow_redirects=True
    )

def test_user_cannot_view_other_users_project(
    client
):

    # ========================================
    # 建立 User A
    # ========================================

    user_a = create_user(
        "user_a@example.com"
    )


    # ========================================
    # User A 的作品
    # ========================================

    project_a = Project(
        user_id=user_a.id,
        topic="User A 的私人作品",
        platform="Instagram",
        tone="專業",
        title="私人作品標題"
    )

    db.session.add(
        project_a
    )

    db.session.commit()

    project_id = project_a.id


    # ========================================
    # 建立 User B
    # ========================================

    create_user(
        "user_b@example.com"
    )


    # ========================================
    # 登入 User B
    # ========================================

    login(
        client,
        "user_b@example.com"
    )


    # ========================================
    # User B 嘗試查看 User A 的作品
    # ========================================

    response = client.get(
        f"/project/{project_id}"
    )


    # 應該看不到
    assert response.status_code == 404
    
def test_user_can_view_own_project(
    client
):

    user = create_user(
        "owner@example.com"
    )

    project = Project(
        user_id=user.id,
        topic="自己的作品",
        platform="Instagram",
        tone="專業",
        title="我的作品"
    )

    db.session.add(
        project
    )

    db.session.commit()

    project_id = project.id


    login(
        client,
        "owner@example.com"
    )


    response = client.get(
        f"/project/{project_id}"
    )


    assert response.status_code == 200