from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CoopTech Mora API"
    api_prefix: str = "/api"
    cors_origins: str = "*"

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_anon_key: str = ""

    model_dir: Path = Path(__file__).resolve().parents[2] / "modelo_mora_produccion"
    # 0 = sin límite (procesa todo el archivo). Ej: 25000 para tope opcional.
    max_upload_rows: int = 0
    sync_supabase_on_upload: bool = False


settings = Settings()
