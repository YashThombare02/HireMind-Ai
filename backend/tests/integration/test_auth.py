import uuid

from httpx import AsyncClient


async def _register(client: AsyncClient, email: str, password: str = "password123", name: str = "Test User"):
    return await client.post("/auth/register", json={"name": name, "email": email, "password": password})


async def _login(client: AsyncClient, email: str, password: str = "password123"):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def test_register_then_login_then_get_me(client: AsyncClient, unique_email: str):
    register_resp = await _register(client, unique_email, name="Priya Sharma")
    assert register_resp.status_code == 201
    body = register_resp.json()
    assert body["email"] == unique_email
    assert body["name"] == "Priya Sharma"
    assert "hashed_password" not in body

    login_resp = await _login(client, unique_email)
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token

    me_resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == unique_email


async def test_register_duplicate_email_returns_400(client: AsyncClient, unique_email: str):
    first = await _register(client, unique_email)
    assert first.status_code == 201

    second = await _register(client, unique_email)
    assert second.status_code == 400
    assert "already exists" in second.json()["detail"]


async def test_register_with_short_password_returns_422(client: AsyncClient, unique_email: str):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test User", "email": unique_email, "password": "short"},
    )
    assert resp.status_code == 422


async def test_login_wrong_password_returns_400(client: AsyncClient, unique_email: str):
    await _register(client, unique_email)
    resp = await _login(client, unique_email, password="wrong-password")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid email or password."


async def test_login_nonexistent_email_returns_400_with_same_message(client: AsyncClient):
    resp = await _login(client, f"nobody-{uuid.uuid4().hex[:8]}@example.com")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid email or password."


async def test_get_me_without_token_returns_401(client: AsyncClient):
    resp = await client.get("/users/me")
    assert resp.status_code == 401


async def test_get_me_with_garbage_token_returns_401(client: AsyncClient):
    resp = await client.get("/users/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


async def test_patch_me_updates_name(client: AsyncClient, unique_email: str):
    await _register(client, unique_email, name="Old Name")
    token = (await _login(client, unique_email)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch("/users/me", json={"name": "New Name"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

    me = await client.get("/users/me", headers=headers)
    assert me.json()["name"] == "New Name"


async def test_rate_limit_trips_on_burst(client: AsyncClient):
    responses = []
    for i in range(11):
        resp = await _register(client, f"burst-{i}-{uuid.uuid4().hex[:6]}@example.com")
        responses.append(resp)

    statuses = [r.status_code for r in responses]
    assert statuses[:10] == [201] * 10, statuses
    assert responses[10].status_code == 429
