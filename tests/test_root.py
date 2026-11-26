from app import create_app


def test_root_endpoint():
    app = create_app({"TESTING": True})

    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.json == {
        "message": "Welcome to Payment Endpoint API!"
    }