# matrices-api

API de la app **MatriCalc** (suma y resta de matrices). Python + FastAPI,
PostgreSQL y RapidOCR (modelos PP-OCR, en el propio servidor) para leer matrices desde fotos. La app está en
`../matrices_app`.

## Desplegado

| | URL |
| --- | --- |
| Landing (descripción, instalar en iPhone / Android / PC) | https://matrices.quantis.site |
| App web / PWA | https://matrices.quantis.site/app/ |
| Publicar APK nuevo | https://matrices.quantis.site/subir |
| API | https://matricesapi.quantis.site |
| Estado de la API | https://matricesapi.quantis.site/health |
| Documentación de la API | https://matricesapi.quantis.site/docs |
| Descarga del APK | https://matricesapi.quantis.site/api/apk/download |

Repos: [matrices-api](https://github.com/dalvarez005/matrices-api) · [matrices-app](https://github.com/dalvarez005/matrices-app).
Servidor: Orange Pi (Docker) detrás del túnel de Cloudflare.

## Qué hace

| Ruta | Sesión | Qué es |
| --- | --- | --- |
| `GET /health` | – | Estado de la base y del OCR. |
| `POST /api/auth/google` | – | `{ "idToken" }` de Google → `{ token, user }` (token de 30 días). |
| `GET /api/auth/me` | sí | Usuario de la sesión. |
| `DELETE /api/auth/me` | sí | Borra la cuenta y su historial. |
| `POST /api/calculate` | opcional | `{ matrices: [A, B, C…], operators: ["+", "-"…], source? }` (2 a 8 matrices del mismo tamaño, un operador entre cada par, de izquierda a derecha) → resultado. También acepta la forma simple `{ operation: "add"\|"subtract", a, b }`. Con sesión se guarda en el historial. |
| `GET /api/history?limit=20&before=<id>` | sí | Historial del usuario, más reciente primero (cada operación trae `matrices` y `operators`). |
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
