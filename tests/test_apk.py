import pytest

KEY = "clave-de-subida-123456"


@pytest.fixture
def apk_client(client, tmp_path, monkeypatch):
    from matrices_api.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "apk_upload_key", KEY)
    return client


def upload(client, data=b"PK\x03\x04contenido", key=KEY, version="1.0.0"):
    return client.post(
        "/api/apk",
        files={"file": ("app.apk", data)},
        data={"version": version, "notes": "Primera versión"},
        headers={"X-Upload-Key": key},
    )


def test_sin_apk(apk_client):
    assert apk_client.get("/api/apk").json() == {"available": False}
    assert apk_client.get("/api/apk/download").status_code == 404


def test_subir_y_descargar(apk_client):
    r = upload(apk_client)
    assert r.status_code == 200 and r.json()["sizeBytes"] == 13
    info = apk_client.get("/api/apk").json()
    assert info["available"] and info["version"] == "1.0.0"
    d = apk_client.get("/api/apk/download")
    assert d.content == b"PK\x03\x04contenido"
    assert "matrices-1.0.0.apk" in d.headers["content-disposition"]


def test_clave_incorrecta_o_archivo_invalido(apk_client):
    assert upload(apk_client, key="otra-clave-cualquiera").status_code == 401
    assert upload(apk_client, data=b"no soy un apk").status_code == 422
    assert apk_client.get("/api/apk").json() == {"available": False}
