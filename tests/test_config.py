from app.core.config import load_settings


def test_settings_load_from_explicit_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=test-file-key\n"
        "DEEPSEEK_FLASH_MODEL=test-flash-model\n",
        encoding="utf-8",
    )

    loaded = load_settings(env_file)

    assert loaded.deepseek_api_key == "test-file-key"
    assert loaded.deepseek_flash_model == "test-flash-model"


def test_process_environment_takes_precedence_over_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=test-file-key\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-process-key")

    loaded = load_settings(env_file)

    assert loaded.deepseek_api_key == "test-process-key"


def test_deepseek_base_url_and_legacy_models_are_normalized(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_FLASH_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_PRO_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n"
        "DEEPSEEK_FLASH_MODEL=deepseek-v4-flash\n"
        "DEEPSEEK_PRO_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )

    loaded = load_settings(env_file)

    assert loaded.deepseek_base_url == "https://api.deepseek.com/v1/chat/completions"
    assert loaded.deepseek_flash_model == "deepseek-chat"
    assert loaded.deepseek_pro_model == "deepseek-chat"
