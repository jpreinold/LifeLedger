import json
import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from deploy.validate_production_config import REQUIRED_TABLES, validate
from deploy.post_deploy_verify import _request_text, _verify_frontend_api


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def production_parameters():
    return json.loads((BACKEND_ROOT / "deploy" / "production.parameters.json").read_text(encoding="utf-8"))


def test_versioned_production_configuration_is_fail_closed_and_complete():
    parameters = production_parameters()

    assert validate(parameters) == []
    assert all(parameters.get(key) for key in REQUIRED_TABLES)
    assert "localhost" not in parameters["CorsAllowedOrigins"]
    assert parameters["AuthMode"] != "local"
    assert parameters["PersistenceMode"] != "local"
    assert parameters["RecordEncryptionMode"] != "disabled"


def test_production_configuration_rejects_local_or_unencrypted_modes():
    for key, unsafe in (
        ("AppEnv", "local"),
        ("AuthMode", "local"),
        ("PersistenceMode", "local"),
        ("RecordEncryptionMode", "disabled"),
        ("CorsAllowedOrigins", "http://localhost:5173"),
    ):
        parameters = production_parameters()
        parameters[key] = unsafe
        assert validate(parameters), key


def test_canonical_deploy_script_never_reads_ignored_samconfig():
    script = (BACKEND_ROOT / "deploy" / "deploy-production.ps1").read_text(encoding="utf-8")
    verifier = (BACKEND_ROOT / "deploy" / "post_deploy_verify.py").read_text(encoding="utf-8")
    requirements = (BACKEND_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "samconfig.production.toml" in script
    assert '"samconfig.toml"' not in script
    assert '"file://$generatedParameterFile"' in script
    assert 'Copy-Item -LiteralPath $parameterFile' in script
    assert '".aws-sam\\production.parameters.yaml"' in script
    assert "ConvertFrom-Json" not in script
    assert "escapedValue" not in script
    assert "validate_production_config.py" in script
    assert "post_deploy_verify.py" in script
    assert "boto3[crt]" in requirements
    assert '"ResponsibilityHistoryTable"' in verifier
    assert '"ResponsibilityHistoryTableName"' not in verifier


def test_version_endpoint_exposes_safe_metadata_only(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_VERSION", "13.0-test")
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    monkeypatch.setenv("BUILD_TIMESTAMP", "2026-07-18T12:00:00Z")
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/version")
    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {
        "app_version": "13.0-test",
        "git_commit": "abc123",
        "environment": "local",
        "build_timestamp": "2026-07-18T12:00:00Z",
    }
    assert set(response.json()) == {"app_version", "git_commit", "environment", "build_timestamp"}


def test_post_deploy_verification_checks_frontend_api_bundle(monkeypatch):
    pages = {
        "https://frontend.example/": '<script type="module" src="/assets/index.js"></script>',
        "https://frontend.example/assets/index.js": 'import("./api.js")',
        "https://frontend.example/assets/api.js": 'const API="https://api.example"',
    }
    monkeypatch.setattr("deploy.post_deploy_verify._request_text", pages.__getitem__)

    _verify_frontend_api("https://frontend.example", "https://api.example")

    try:
        _verify_frontend_api("https://frontend.example", "https://wrong.example")
    except RuntimeError as exc:
        assert "expected API URL" in str(exc)
    else:
        raise AssertionError("Frontend API drift should fail deployment verification")


def test_post_deploy_frontend_check_uses_stable_verifier_identity(monkeypatch):
    captured = {}

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def open_request(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response(b"ok")

    monkeypatch.setattr("deploy.post_deploy_verify.urllib.request.urlopen", open_request)

    assert _request_text("https://frontend.example/") == "ok"
    assert captured["request"].get_header("User-agent") == "LifeLedgerDeploymentVerifier/1.0"
    assert captured["timeout"] == 15
