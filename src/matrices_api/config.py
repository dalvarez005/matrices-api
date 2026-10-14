from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración por variables de entorno (o archivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos: mismo PostgreSQL y usuario que Yankees, otra base.
    # DATABASE_URL, si se define, reemplaza a los DB_* (p. ej. en pruebas).
    database_url: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "matrices"
    db_user: str = "quantis"
    db_password: str = ""

    # Firma de los tokens de sesión (mínimo 32 caracteres).
    jwt_secret: str = ""
    jwt_days: int = 30

    # Client IDs de Google aceptados como "aud" del idToken, separados por
    # coma: el web (que usan web, Android e iOS) y, si se quiere, el de iOS.
    google_client_ids: str = ""

    # Orígenes de la app web, separados por coma (https://matrices.dominio).
    cors_origins: str = ""
    # Permite http://localhost:<puerto> (flutter run -d chrome).
    cors_allow_localhost: bool = False

    # OCR de fotos de matrices.
    ocr_enabled: bool = True
    ocr_timeout_seconds: int = 20
    ocr_max_concurrency: int = 1
    max_upload_mb: int = 8

    # APK de Android que se descarga desde la landing.
    data_dir: str = "data"
    # Clave para subir un APK nuevo (mínimo 16 caracteres; vacía = deshabilitado).
    apk_upload_key: str = ""
    max_apk_mb: int = 150

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        from sqlalchemy import URL

        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    @property
    def google_client_id_list(self) -> list[str]:
        return [c.strip() for c in self.google_client_ids.split(",") if c.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres.")
    return settings
