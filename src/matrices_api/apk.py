"""APK de Android: se sube con una clave y la landing lo ofrece para descargar.

Se guarda en DATA_DIR/apk (un volumen de Docker): matrices.apk e info.json.
"""

import hmac
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .config import get_settings

router = APIRouter(prefix="/api/apk", tags=["apk"])


def _dir() -> Path:
    path = Path(get_settings().data_dir) / "apk"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _info() -> dict | None:
    try:
        return json.loads((_dir() / "info.json").read_text())
    except (FileNotFoundError, ValueError):
        return None


@router.get("")
def apk_info():
    """Datos del APK publicado (la landing los muestra en el botón)."""
    info = _info()
    if info is None or not (_dir() / "matrices.apk").exists():
        return {"available": False}
    return {"available": True, **info}


@router.get("/download")
def apk_download():
    info = _info()
    path = _dir() / "matrices.apk"
    if info is None or not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Todavía no hay un APK publicado.")
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename=f"matrices-{info['version']}.apk",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("")
async def apk_upload(
    file: UploadFile,
    version: str = Form(min_length=1, max_length=30),
    notes: str = Form("", max_length=500),
    x_upload_key: str = Header(""),
):
    settings = get_settings()
    key = settings.apk_upload_key
    if len(key) < 16:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La subida de APK no está configurada.")
    if not hmac.compare_digest(x_upload_key.encode(), key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clave de subida incorrecta.")

    limit = settings.max_apk_mb * 1024 * 1024
    folder = _dir()
    size = 0
    # Se escribe a un temporal y se reemplaza al final: una subida cortada no
    # deja un APK roto publicado.
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            first = True
            while chunk := await file.read(1024 * 1024):
                if first and not chunk.startswith(b"PK"):
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El archivo no es un APK.")
                first = False
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE, f"El APK supera {settings.max_apk_mb} MB."
                    )
                out.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El archivo está vacío.")
        os.replace(tmp, folder / "matrices.apk")
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    info = {
        "version": version.strip(),
        "notes": notes.strip(),
        "sizeBytes": size,
        "uploadedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (folder / "info.json").write_text(json.dumps(info))
    return {"available": True, **info}
