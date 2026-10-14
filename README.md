# matrices-api

API de la app **Matrices** (suma y resta de matrices). Python + FastAPI,
PostgreSQL y RapidOCR (modelos PP-OCR, en el propio servidor) para leer matrices desde fotos. La app está en
`../matrices_app`.

## Qué hace

| Ruta | Sesión | Qué es |
| --- | --- | --- |
| `GET /health` | – | Estado de la base y del OCR. |
| `POST /api/auth/google` | – | `{ "idToken" }` de Google → `{ token, user }` (token de 30 días). |
| `GET /api/auth/me` | sí | Usuario de la sesión. |
| `DELETE /api/auth/me` | sí | Borra la cuenta y su historial. |
| `POST /api/calculate` | opcional | `{ operation: "add"\|"subtract", a, b, source? }` → resultado. Con sesión se guarda en el historial. |
| `GET /api/history?limit=20&before=<id>` | sí | Historial del usuario, más reciente primero. |
| `DELETE /api/history/{id}` / `DELETE /api/history` | sí | Borrar una / todas. |
| `POST /api/ocr` | opcional | Foto (`file`, multipart) → una o dos matrices detectadas, celdas ilegibles en `null`. |

Las matrices viajan como texto (`[["1", "-2.5"], ["3/4", "0"]]`). El cálculo
es exacto (fracciones): `0.1 + 0.2 = 0.3`; si alguna celda es fracción, el
resultado va en fracciones. Máximo 10×10. Los errores llegan como
`{ "detail": "mensaje" }` listo para mostrar.

Documentación interactiva: `http://localhost:5120/docs`.

## Desarrollo

```bash
uv sync
cp .env.example .env    # completar DB_PASSWORD, JWT_SECRET, GOOGLE_CLIENT_IDS
                        # y CORS_ALLOW_LOCALHOST=true
uv run matrices-api     # http://localhost:5120 con recarga
uv run pytest           # pruebas (usan SQLite, no tocan PostgreSQL)
```

Sin PostgreSQL a mano: `DATABASE_URL=sqlite:///dev.db uv run matrices-api`.
El OCR (RapidOCR) descarga sus modelos (~30 MB) la primera vez que se usa.

## Despliegue

En la Orange Pi, junto a Yankees: [docs/DEPLOY.md](docs/DEPLOY.md).
