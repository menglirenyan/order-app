import os
from dataclasses import dataclass
from pathlib import Path

from starlette.config import Config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
LEGACY_DEEPSEEK_MODELS = {
    "deepseek-v4-flash": DEFAULT_DEEPSEEK_MODEL,
    "deepseek-v4-pro": DEFAULT_DEEPSEEK_MODEL,
}


def normalize_deepseek_api_url(value: str) -> str:
    base_url = str(value or DEFAULT_DEEPSEEK_BASE_URL).strip().rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def normalize_deepseek_model(value: str) -> str:
    model = str(value or DEFAULT_DEEPSEEK_MODEL).strip()
    return LEGACY_DEEPSEEK_MODELS.get(model, model)


def readable_env_file(env_file: Path) -> Path | None:
    if env_file.is_file() and os.access(env_file, os.R_OK):
        return env_file
    return None


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_flash_model: str
    deepseek_pro_model: str
    static_dir: Path
    template_dir: Path
    upload_dir: Path


def load_settings(env_file: Path = DEFAULT_ENV_FILE) -> Settings:
    config = Config(env_file=readable_env_file(env_file))
    return Settings(
        database_url=config("DATABASE_URL", default="sqlite:///./orders.db"),
        secret_key=config("SECRET_KEY", default="dev-secret-key"),
        deepseek_api_key=config("DEEPSEEK_API_KEY", default="").strip(),
        deepseek_base_url=normalize_deepseek_api_url(
            config("DEEPSEEK_BASE_URL", default=DEFAULT_DEEPSEEK_BASE_URL)
        ),
        deepseek_flash_model=normalize_deepseek_model(
            config("DEEPSEEK_FLASH_MODEL", default=DEFAULT_DEEPSEEK_MODEL)
        ),
        deepseek_pro_model=normalize_deepseek_model(
            config("DEEPSEEK_PRO_MODEL", default=DEFAULT_DEEPSEEK_MODEL)
        ),
        static_dir=Path(config("STATIC_DIR", default="app/static")),
        template_dir=Path(config("TEMPLATE_DIR", default="app/templates")),
        upload_dir=Path(config("UPLOAD_DIR", default="app/static/uploads")),
    )


settings = load_settings()
