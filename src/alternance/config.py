from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8")

    lba_api_base_url: str = "https://api.apprentissage.beta.gouv.fr/api"
    lba_api_key: str = ""

    duckdb_path: str = "data/alternance.duckdb"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "alternance"

    @property
    def has_api_key(self) -> bool:
        return bool(self.lba_api_key)

    @property
    def duckdb_file(self) -> Path:
        path = Path(self.duckdb_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path


settings = Settings()
