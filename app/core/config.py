import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_environment_file() -> None:
    """Load the correct dotenv file for local development only.

    Runtime platforms inject env directly:
    - Docker Compose passes environment/env_file values.
    - AKS receives values from Kubernetes Secrets generated from Key Vault.
    - EC2/systemd can pass values from its own environment.

    ENV_FILE is an explicit override. Otherwise ENVIRONMENT selects .env.<env>
    before falling back to .env.
    """
    env_file = os.getenv("ENV_FILE")
    if env_file:
        load_dotenv(env_file)
        return

    environment = os.getenv("ENVIRONMENT", "development")
    candidate = Path(f".env.{environment}")
    if candidate.exists():
        load_dotenv(candidate)
        return

    load_dotenv()


_load_environment_file()


def _secret(name: str, default: str | None = None, *, required: bool = False) -> str:
    """Read a config value from NAME or NAME_FILE.

    NAME_FILE supports Docker/Kubernetes mounted secrets, including Azure Key
    Vault CSI Driver volumes. Environment variables continue to work for local
    Docker and CI, so the application code does not depend on Azure SDKs.
    """
    file_name = os.getenv(f"{name}_FILE")
    if file_name:
        value = Path(file_name).read_text(encoding="utf-8").strip()
    else:
        value = os.getenv(name, default)

    if required and not value:
        raise RuntimeError(f"{name} is not set")

    return value or ""


def _int(name: str, default: int) -> int:
    return int(_secret(name, str(default)))


def _bool(name: str, default: bool = False) -> bool:
    value = _secret(name)
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    service_name: str = _secret("SERVICE_NAME", "invoice-service")
    environment: str = _secret("ENVIRONMENT", "development")
    log_level: str = _secret("LOG_LEVEL", "INFO")
    database_url: str = _secret("DATABASE_URL", required=True)
    database_pool_size: int = _int("DATABASE_POOL_SIZE", 5)
    database_max_overflow: int = _int("DATABASE_MAX_OVERFLOW", 10)
    database_pool_recycle_seconds: int = _int("DATABASE_POOL_RECYCLE_SECONDS", 1800)
    database_pool_pre_ping: bool = _bool("DATABASE_POOL_PRE_PING", True)
    jwt_secret_key: str = _secret("JWT_SECRET_KEY", required=True)
    rabbitmq_url: str = _secret("RABBITMQ_URL", required=True)
    order_service_url: str = _secret("ORDER_SERVICE_URL", required=True)
    auth_service_url: str = _secret("AUTH_SERVICE_URL", required=True)
    api_version: str = _secret("API_VERSION", "/api/v1")
    storage_provider: str = _secret("STORAGE_PROVIDER", "local")
    local_storage_root: str = _secret("LOCAL_STORAGE_ROOT", "/var/lib/opslora/invoice-service/storage")
    azure_storage_account_url: str = _secret("AZURE_STORAGE_ACCOUNT_URL", "")
    azure_storage_container: str = _secret("AZURE_STORAGE_CONTAINER", "invoice-pdfs")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
