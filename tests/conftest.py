import os
import tempfile

import pytest

# Antes de importar la app: SQLite en un archivo temporal, sin PostgreSQL.
_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ["JWT_SECRET"] = "x" * 40
os.environ["GOOGLE_CLIENT_IDS"] = "web-client"


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from matrices_api import app as main

    def fake_verify(token: str) -> dict:
        return {"sub": token, "email": f"{token}@test.com", "name": token.title(), "email_verified": True}

    monkeypatch.setattr(main, "verify_google_token", fake_verify)
    with TestClient(main.app) as c:
        yield c


def login(client, who="usuario-uno") -> dict:
    token = client.post("/api/auth/google", json={"idToken": f"token-de-{who}"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}
