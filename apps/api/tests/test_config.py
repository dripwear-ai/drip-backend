import pytest
from drip.core.config import DEFAULT_ENV_FILE, Settings
from pydantic import ValidationError


def production(**overrides):
    values = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "synthetic-test-signing-material-only-123456789",
        "DATABASE_URL": "postgresql+asyncpg://service:synthetic-db-value@db/drip",
        "REDIS_URL": "redis://:synthetic-cache-value@cache/0",
        "DEBUG": False,
    }
    return Settings(_env_file=None, **(values | overrides))


def test_settings_defaults(monkeypatch):
    # The test harness pins effective URLs to disposable targets. Test model
    # defaults independently of those process overrides, without creating clients.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    settings = Settings(_env_file=None, ENVIRONMENT="development")
    assert settings.is_development
    assert not settings.is_production
    assert "localhost:5435/" in settings.DATABASE_URL
    assert "localhost:6381/" in settings.REDIS_URL
    assert "http://localhost:3000" in settings.cors_origins_list
    assert "http://localhost:3001" in settings.cors_origins_list
    assert "http://localhost:3002" in settings.cors_origins_list
    assert "http://localhost:8083" in settings.cors_origins_list


def test_environment_file_is_root_and_independent_of_working_directory(tmp_path, monkeypatch):
    assert DEFAULT_ENV_FILE.name == ".env"
    assert (DEFAULT_ENV_FILE.parent / "pnpm-workspace.yaml").is_file()
    monkeypatch.chdir(tmp_path)
    assert DEFAULT_ENV_FILE.is_absolute()


def test_explicit_dotenv_and_process_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("VERSION=dotenv-value\nDEBUG=false\n", encoding="utf-8")
    child = tmp_path / "nested"
    child.mkdir()
    monkeypatch.chdir(child)
    assert Settings(_env_file=env_file).VERSION == "dotenv-value"
    monkeypatch.setenv("VERSION", "process-value")
    assert Settings(_env_file=env_file).VERSION == "process-value"


def test_settings_secret_key_validation():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY="short_key")


@pytest.mark.parametrize("environment", ["production", " PRODUCTION ", "Production"])
def test_production_normalizes_and_succeeds(environment):
    settings = production(ENVIRONMENT=environment)
    assert settings.is_production
    assert settings.ENVIRONMENT == "production"


@pytest.mark.parametrize("environment", ["prod", "produciton", "", "testing"])
def test_unknown_environment_fails(environment):
    with pytest.raises(ValidationError):
        production(ENVIRONMENT=environment)


@pytest.mark.parametrize(
    "overrides",
    [
        {"SECRET_KEY": "dev_secret_key_still_present_in_prod_test_string_32"},
        {"DEBUG": True},
        {"LOG_LEVEL": " debug "},
        {"DATABASE_URL": "postgresql+asyncpg://drip_user:drip_password@db/drip"},
        {"DATABASE_URL": "postgresql+asyncpg://drip_user:drip%5Fpassword@db/drip"},
        {"DATABASE_URL": "postgresql+asyncpg://service@db/drip"},
        {"REDIS_URL": "redis://cache/0"},
        {"REDIS_URL": "redis://:password@cache/0"},
    ],
)
def test_production_rejects_unsafe_configuration_on_construction(overrides):
    with pytest.raises(ValidationError):
        production(**overrides)


def test_validation_exception_does_not_print_secret_input():
    with pytest.raises(ValidationError) as exc:
        production(SECRET_KEY="sensitive-short")
    assert "sensitive-short" not in str(exc.value)
