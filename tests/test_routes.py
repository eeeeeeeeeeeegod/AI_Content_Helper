
def test_health(client):

    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    assert response.get_json() == {
        "status": "ok"
    }


def test_login_page(client):

    response = client.get(
        "/login"
    )

    assert response.status_code == 200

    assert "登入".encode("utf-8") in response.data


def test_register_page(client):

    response = client.get(
        "/register"
    )

    assert response.status_code == 200

    assert "建立帳號".encode("utf-8") in response.data


def test_history_requires_login(client):

    response = client.get(
        "/history",
        follow_redirects=False
    )

    assert response.status_code == 302

    assert "/login" in response.headers["Location"]


def test_index_requires_login(client):

    response = client.get(
        "/",
        follow_redirects=False
    )

    assert response.status_code == 302

    assert "/login" in response.headers["Location"]