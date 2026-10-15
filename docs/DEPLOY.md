# Despliegue en la Orange Pi

Igual que Yankees: la API corre en Docker y usa el PostgreSQL que ya existe
en el servidor (mismo usuario `quantis`, **base nueva `matrices`**).

| | Yankees | MatriCalc |
| --- | --- | --- |
| API | `~/yankees-api`, puerto 5114 | `~/matrices-api`, puerto **5120** |
| Web | `~/yankees-web`, puerto 5180 | `~/matrices-web`, puerto **5190** |
| Base | `yankees_management` | `matrices` |

## 1. Crear la base (una vez, en el servidor)

```bash
sudo -u postgres psql -c "CREATE DATABASE matrices OWNER quantis;"
```

En `pg_hba.conf` agregar la línea para la base nueva (la de Yankees solo
cubre `yankees_management`) y recargar:

```
host matrices quantis 172.16.0.0/12 scram-sha-256
```

```bash
sudo systemctl reload postgresql
```

Las tablas (`users`, `operations`) las crea la API al arrancar.

## 2. Publicar la API (desde la PC)

```bash
deploy/deploy.sh orangepi@192.168.1.77
```

Copia el código con rsync a `~/matrices-api` y construye la imagen **en la
Orange Pi** (ARM nativo: no hace falta Docker ni emulación en la PC).

La primera vez, en el servidor:

```bash
cd ~/matrices-api
cp .env.example .env && chmod 600 .env
nano .env        # DB_PASSWORD = la de quantis (la misma de ~/yankees-api/.env)
                 # JWT_SECRET  = openssl rand -base64 48
                 # APK_UPLOAD_KEY = openssl rand -base64 24
docker compose up -d --build
curl http://localhost:5120/health   # {"status":"ok","db":true,"ocr":true}
```

Si `/health` dice `"db": false`, casi siempre es `pg_hba.conf` (paso 1).

## APK de Android

La landing (`matrices.quantis.site`) ofrece el APK publicado. Para subir uno
nuevo: `https://matrices.quantis.site/subir` (pide `APK_UPLOAD_KEY`), o desde
la PC:

```bash
APK_UPLOAD_KEY=... deploy/upload-apk.sh ../matrices_app/build/app/outputs/flutter-apk/app-release.apk 1.0.1 "Novedades"
```

Se guarda en la memoria USB de 32 GB, junto a Minecraft
(`DATA_PATH=/mnt/minecraft-usb/matrices/data` en `.env`), para no llenar el
disco interno de 7 GB. La carpeta debe pertenecer al usuario del contenedor
(uid 1654). Sobrevive a actualizaciones de la API.

## 3. Dominio (Cloudflare)

En el mismo túnel de Yankees, dos hostnames públicos:

- `matricesapi.quantis.site` → `http://localhost:5120`
- `matrices.quantis.site` → `http://localhost:5190` (la web, ver `../matrices_app`)

y en `.env`: `CORS_ORIGINS=https://matrices.quantis.site`. Si usas otros
dominios, cámbialos también en `matrices_app/lib/app/env.dart` y
`web/index.html`.

## Día a día

```bash
deploy/deploy.sh                      # publicar una versión nueva
ssh orangepi@192.168.1.77
cd ~/matrices-api
docker compose logs -f api            # logs
docker compose restart api
```

El OCR usa un núcleo por foto (`OCR_MAX_CONCURRENCY=1`): si dos personas
suben fotos a la vez, la segunda espera unos segundos.
