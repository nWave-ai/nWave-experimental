"""Behavioral checks for the shipped Jev decision invoker."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError, URLError


_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "nWave/skills/nw-typesafe-system-one/scripts/jev_decide.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("jev_decide", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "state": {"candidate": "one"},
                "model": "jev-1.13.0",
                "questions": {
                    "next": {
                        "type": "choice",
                        "instructions": "select one",
                        "criteria": {"a": "A", "insufficient": "unknown"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _mock_http_error(code: int) -> HTTPError:
    """Create a mock HTTPError with the given status code."""
    return HTTPError("url", code, "message", {}, None)


def test_missing_key_is_a_loud_local_fallback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    assert _module().main(["--request", str(request), "--output", str(output)]) == 3

    assert "TYPESAFE_API_KEY is absent" in capsys.readouterr().err
    assert not output.exists()


def test_typed_response_is_saved_without_exposing_credentials(
    tmp_path: Path, monkeypatch
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret-not-to-be-written")
    module = _module()
    observed: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"model":"jev-1.13.0","answers":{"next":{"type":"choice","choice":"a"}}}'

    def fake_urlopen(http_request, timeout):
        observed["authorization"] = http_request.get_header("Authorization")
        observed["payload"] = json.loads(http_request.data)
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)

    assert module.main(["--request", str(request), "--output", str(output)]) == 0

    assert observed["authorization"] == "Bearer secret-not-to-be-written"
    assert observed["payload"] == json.loads(request.read_text(encoding="utf-8"))
    assert (
        json.loads(output.read_text(encoding="utf-8"))["answers"]["next"]["choice"]
        == "a"
    )
    assert "secret-not-to-be-written" not in output.read_text(encoding="utf-8")


def test_malformed_question_is_refused_before_any_network_request(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    request.write_text(
        json.dumps(
            {
                "state": {"candidate": "one"},
                "model": "jev-1.13.0",
                "questions": {"next": {"type": "choice", "instructions": "select"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")

    assert _module().main(["--request", str(request), "--output", str(output)]) == 2

    assert "non-empty criteria" in capsys.readouterr().err
    assert not output.exists()


def test_http_400_caller_schema_error_returns_exit_2(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_400(http_request, timeout):
        raise _mock_http_error(400)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_400)

    assert module.main(["--request", str(request), "--output", str(output)]) == 2

    assert "HTTP 400" in capsys.readouterr().err
    assert not output.exists()


def test_http_422_unprocessable_entity_returns_exit_2(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_422(http_request, timeout):
        raise _mock_http_error(422)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_422)

    assert module.main(["--request", str(request), "--output", str(output)]) == 2

    assert "HTTP 422" in capsys.readouterr().err
    assert not output.exists()


def test_http_401_unauthorized_returns_exit_5(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "invalid_key")
    module = _module()

    def fake_urlopen_401(http_request, timeout):
        raise _mock_http_error(401)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_401)

    assert module.main(["--request", str(request), "--output", str(output)]) == 5

    assert "HTTP 401" in capsys.readouterr().err
    assert not output.exists()


def test_http_403_forbidden_returns_exit_5(tmp_path: Path, monkeypatch, capsys) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_403(http_request, timeout):
        raise _mock_http_error(403)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_403)

    assert module.main(["--request", str(request), "--output", str(output)]) == 5

    assert "HTTP 403" in capsys.readouterr().err
    assert not output.exists()


def test_http_408_request_timeout_returns_exit_3(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_408(http_request, timeout):
        raise _mock_http_error(408)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_408)

    assert module.main(["--request", str(request), "--output", str(output)]) == 3

    assert "HTTP 408" in capsys.readouterr().err
    assert not output.exists()


def test_http_429_rate_limit_returns_exit_3(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_429(http_request, timeout):
        raise _mock_http_error(429)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_429)

    assert module.main(["--request", str(request), "--output", str(output)]) == 3

    assert "HTTP 429" in capsys.readouterr().err
    assert not output.exists()


def test_http_503_service_unavailable_returns_exit_3(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_503(http_request, timeout):
        raise _mock_http_error(503)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_503)

    assert module.main(["--request", str(request), "--output", str(output)]) == 3

    assert "HTTP 503" in capsys.readouterr().err
    assert not output.exists()


def test_http_500_server_error_returns_exit_3(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_500(http_request, timeout):
        raise _mock_http_error(500)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_500)

    assert module.main(["--request", str(request), "--output", str(output)]) == 3

    assert "HTTP 500" in capsys.readouterr().err
    assert not output.exists()


def test_http_502_bad_gateway_returns_exit_3(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_502(http_request, timeout):
        raise _mock_http_error(502)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_502)

    assert module.main(["--request", str(request), "--output", str(output)]) == 3

    assert "HTTP 502" in capsys.readouterr().err
    assert not output.exists()


def test_http_404_not_found_returns_exit_4(tmp_path: Path, monkeypatch, capsys) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_404(http_request, timeout):
        raise _mock_http_error(404)

    monkeypatch.setattr(module, "urlopen", fake_urlopen_404)

    assert module.main(["--request", str(request), "--output", str(output)]) == 4

    assert "HTTP 404" in capsys.readouterr().err
    assert not output.exists()


def test_network_timeout_returns_exit_3(tmp_path: Path, monkeypatch, capsys) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_timeout(http_request, timeout):
        raise URLError(TimeoutError("timed out"))

    monkeypatch.setattr(module, "urlopen", fake_urlopen_timeout)

    assert module.main(["--request", str(request), "--output", str(output)]) == 3

    assert "unavailable" in capsys.readouterr().err
    assert not output.exists()


def test_dns_error_returns_exit_3(tmp_path: Path, monkeypatch, capsys) -> None:
    import socket
    from urllib.error import URLError

    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    def fake_urlopen_dns_error(http_request, timeout):
        raise URLError(socket.gaierror("Name or service not known"))

    monkeypatch.setattr(module, "urlopen", fake_urlopen_dns_error)

    assert module.main(["--request", str(request), "--output", str(output)]) == 3

    assert "unavailable" in capsys.readouterr().err
    assert not output.exists()


def test_invalid_json_response_returns_exit_4(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"not valid json at all"

    def fake_urlopen_invalid_json(http_request, timeout):
        return Response()

    monkeypatch.setattr(module, "urlopen", fake_urlopen_invalid_json)

    assert module.main(["--request", str(request), "--output", str(output)]) == 4

    assert "invalid response JSON" in capsys.readouterr().err
    assert not output.exists()


def test_response_missing_answers_returns_exit_4(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"model":"jev-1.13.0"}'

    def fake_urlopen_no_answers(http_request, timeout):
        return Response()

    monkeypatch.setattr(module, "urlopen", fake_urlopen_no_answers)

    assert module.main(["--request", str(request), "--output", str(output)]) == 4

    assert "no typed answers" in capsys.readouterr().err
    assert not output.exists()


def test_response_read_timeout_is_unavailable_without_a_result(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    _request(request)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    module = _module()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            raise TimeoutError("read timed out")

    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: Response())

    assert module.main(["--request", str(request), "--output", str(output)]) == 3
    assert "unavailable" in capsys.readouterr().err
    assert not output.exists()
