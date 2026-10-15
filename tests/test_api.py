from conftest import login


def test_health(client):
    assert client.get("/health").json()["db"] is True


def test_calcular_sin_cuenta_no_guarda(client):
    r = client.post("/api/calculate", json={"operation": "add", "a": [["1"]], "b": [["2"]]})
    assert r.status_code == 200
    assert r.json()["result"] == [["3"]] and r.json()["id"] is None
    assert client.get("/api/history").status_code == 401


def test_error_de_tamano(client):
    r = client.post("/api/calculate", json={"operation": "add", "a": [["1", "2"]], "b": [["2"]]})
    assert r.status_code == 422 and "mismo tamaño" in r.json()["detail"]


def test_historial_por_usuario(client):
    uno, dos = login(client, "uno"), login(client, "dos")
    for i in range(3):
        client.post(
            "/api/calculate",
            json={"operation": "subtract", "a": [[str(i)]], "b": [["1"]]},
            headers=uno,
        )
    client.post("/api/calculate", json={"operation": "add", "a": [["5"]], "b": [["5"]]}, headers=dos)

    page = client.get("/api/history?limit=2", headers=uno).json()
    assert [o["result"] for o in page["items"]] == [[["1"]], [["0"]]]
    rest = client.get(f"/api/history?limit=2&before={page['nextBefore']}", headers=uno).json()
    assert [o["result"] for o in rest["items"]] == [[["-1"]]] and rest["nextBefore"] is None

    otro = client.get("/api/history", headers=dos).json()["items"]
    assert len(otro) == 1
    # No se puede borrar lo de otro usuario.
    assert client.delete(f"/api/history/{otro[0]['id']}", headers=uno).status_code == 404
    assert client.delete(f"/api/history/{otro[0]['id']}", headers=dos).status_code == 204

    assert client.delete("/api/history", headers=uno).status_code == 204
    assert client.get("/api/history", headers=uno).json()["items"] == []


def test_me_y_borrar_cuenta(client):
    h = login(client, "tres")
    assert client.get("/api/auth/me", headers=h).json()["email"] == "token-de-tres@test.com"
    assert client.delete("/api/auth/me", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_token_invalido(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_operacion_compuesta_en_historial(client):
    h = login(client, "cuatro")
    body = {"matrices": [[["1"]], [["2"]], [["4"]]], "operators": ["+", "-"], "source": "image"}
    r = client.post("/api/calculate", json=body, headers=h)
    assert r.status_code == 200
    out = r.json()
    assert out["result"] == [["-1"]] and out["operation"] == "compound"
    assert out["a"] == [["1"]] and out["b"] == [["2"]]

    item = client.get("/api/history", headers=h).json()["items"][0]
    assert item["matrices"] == body["matrices"] and item["operators"] == ["+", "-"]
    assert item["source"] == "image"

    # La forma simple sigue funcionando y también trae la expresión.
    simple = client.post("/api/calculate", json={"operation": "subtract", "a": [["5"]], "b": [["2"]]}).json()
    assert simple["matrices"] == [[["5"]], [["2"]]] and simple["operators"] == ["-"]


def test_operacion_compuesta_invalida(client):
    r = client.post("/api/calculate", json={"matrices": [[["1"]], [["2"]], [["3"]]], "operators": ["+"]})
    assert r.status_code == 422
    r = client.post("/api/calculate", json={"matrices": [[["1"]], [["2"]], [["3", "4"]]], "operators": ["+", "+"]})
    assert r.status_code == 422 and "C es 1x2" in r.json()["detail"]
    assert client.post("/api/calculate", json={"source": "manual"}).status_code == 422


def test_migra_tabla_anterior(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from matrices_api.db import _add_missing_columns

    engine = create_engine(f"sqlite:///{tmp_path / 'vieja.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE operations (id INTEGER PRIMARY KEY, operation VARCHAR(10))"))
    _add_missing_columns(engine)
    _add_missing_columns(engine)  # idempotente
    columns = {c["name"] for c in inspect(engine).get_columns("operations")}
    assert {"matrices", "operators"} <= columns
