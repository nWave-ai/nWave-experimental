"""Consumer-visible wire checks for the shipped Jev CLI; loopback only."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "nWave/skills/nw-typesafe-system-one/scripts/jev_decide.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("jev_decide", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request():
    return {
        "state": {"authorized": "minimal reviewer-owned evidence"},
        "model": "jev-latest",
        "questions": {
            "applicable": {
                "type": "choice",
                "criteria": {"yes": None, "insufficient": {"when": "missing evidence"}},
            },
            "quality": {
                "type": "score",
                "instructions": {"task": "rate ownership"},
                "criteria": ["duplicate owner", "existing owner"],
            },
            "supported": {
                "type": "noul",
                "instructions": ["Is the recovery observed?"],
                "criteria": {"true": "observed", "false": None},
            },
        },
    }


def _response():
    return {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 120, "output_tokens": 12},
        "answers": {
            "applicable": {
                "type": "choice",
                "choice": "yes",
                "confidence": 0.8,
                "probabilities": {"yes": 0.8, "insufficient": 0.2},
            },
            "quality": {
                "type": "score",
                "score": 0.75,
                "confidence": 0.35,
                "legend": {"0": "duplicate owner", "1": "existing owner"},
                "probabilities": {"0": 0.25, "1": 0.75},
            },
            "supported": {"type": "noul", "noul": 0.98},
        },
        "remote_metadata": {"retained": True},
    }


@pytest.fixture
def wire(monkeypatch):
    """Run controlled HTTP responses, never the paid service."""
    state = {"status": 200, "body": json.dumps(_response()).encode(), "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["requests"].append(
                self.rfile.read(int(self.headers["Content-Length"]))
            )
            self.send_response(state["status"])
            self.end_headers()
            self.wfile.write(state["body"])

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("TYPESAFE_API_KEY", "local-test-key-not-a-credential")
    state["endpoint"] = f"http://127.0.0.1:{server.server_port}/v1/systemone"
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _invoke(tmp_path, wire, request=None):
    path, output = tmp_path / "request.json", tmp_path / "result.json"
    # Noncanonical whitespace must remain exactly as authored over the transport.
    path.write_text(
        json.dumps(request if request is not None else _request(), indent=3),
        encoding="utf-8",
    )
    code = _module().main(
        [
            "--request",
            str(path),
            "--output",
            str(output),
            "--endpoint",
            wire["endpoint"],
        ]
    )
    return code, path, output


def test_mixed_batch_keeps_authored_request_and_raw_response(tmp_path, wire, capsys):
    code, path, output = _invoke(tmp_path, wire)
    assert code == 0
    assert wire["requests"] == [path.read_bytes()]
    assert output.read_bytes() == wire["body"]
    assert "local-test-key" not in output.read_text() + capsys.readouterr().out


def test_stdio_exchange_needs_no_files(tmp_path, wire):
    """A role without file-write permission sends the request on stdin, reads stdout."""
    authored = json.dumps(_request(), indent=3).encode()
    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), "--request", "-", "--output", "-"]
        + ["--endpoint", wire["endpoint"]],
        input=authored,
        capture_output=True,
        cwd=tmp_path,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert wire["requests"] == [authored]
    assert completed.stdout == wire["body"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "criteria", [["single"], ["low", {"level": "medium"}, ["high"]]]
)
def test_score_order_and_structured_levels_survive(tmp_path, wire, criteria):
    request = _request()
    request["questions"] = {"quality": {"type": "score", "criteria": criteria}}
    response = _response()
    response["answers"] = {
        "quality": {
            "type": "score",
            "score": len(criteria) - 1,
            "confidence": 1,
            "legend": {str(i): level for i, level in enumerate(criteria)},
            "probabilities": {
                str(i): int(i == len(criteria) - 1) for i in range(len(criteria))
            },
        }
    }
    wire["body"] = json.dumps(response).encode()
    assert _invoke(tmp_path, wire, request)[0] == 0


@pytest.mark.parametrize(
    "case",
    [
        (("answers",), {}, "question identifiers"),
        (
            ("answers", "unexpected"),
            {"type": "noul", "noul": 1},
            "question identifiers",
        ),
        (("answers", "quality", "type"), "choice", "type must match"),
        (("answers", "quality", "score"), 2, "score must be"),
        (("answers", "quality", "score"), 0.1, "probability-weighted"),
        (("answers", "quality", "legend", "0"), "rewritten rubric", "legend"),
        (
            ("answers", "quality", "probabilities"),
            {"0": 0.2, "1": 0.2},
            "sum approximately",
        ),
        (
            ("answers", "quality", "probabilities"),
            {"0": 0, "2": 1},
            "match requested criteria",
        ),
        (("answers", "applicable", "choice"), "insufficient", "highest probability"),
        (("answers", "applicable", "choice"), "other", "requested label"),
        (("answers", "applicable", "confidence"), True, "finite number"),
        (("answers", "supported", "noul"), -0.1, "finite number"),
        (("answers", "quality", "confidence"), float("nan"), "invalid response JSON"),
        (("model",), "", "model"),
        (("usage",), None, "usage"),
        (("usage", "input_tokens"), True, "nonnegative integer"),
        (("usage", "output_tokens"), -1, "nonnegative integer"),
    ],
)
def test_service_defects_reject_without_a_judgment(tmp_path, wire, capsys, case):
    path, value, diagnostic = case
    response = copy.deepcopy(_response())
    target = response
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    wire["body"] = json.dumps(response).encode()
    code, _, output = _invoke(tmp_path, wire)
    assert code == 4
    assert diagnostic in capsys.readouterr().err
    assert not output.exists()
    assert len(wire["requests"]) == 1


@pytest.mark.parametrize(
    "body", [b"not json", b"\xff", b'{"answers":{},"answers":{}}', b'{"model":1e999}']
)
def test_ambiguous_or_nonfinite_json_is_not_a_result(tmp_path, wire, body):
    wire["body"] = body
    code, _, output = _invoke(tmp_path, wire)
    assert code == 4
    assert not output.exists()


@pytest.mark.parametrize(
    "path,value",
    [
        (("questions", "quality", "criteria"), {"0": "bad", "1": "good"}),
        (("questions", "quality", "criteria"), []),
        (("questions", "quality", "criteria"), [None]),
        (("questions", "quality", "type"), "Score"),
        (("questions", "supported", "criteria"), {"yes": "not noul"}),
        (("state",), None),
        (("model",), 5),
        (("questions", "supported", "instructions"), 3),
    ],
)
def test_caller_defects_never_reach_network_even_without_key(
    tmp_path, wire, monkeypatch, path, value
):
    request = _request()
    target = request
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    monkeypatch.delenv("TYPESAFE_API_KEY")
    code, _, output = _invoke(tmp_path, wire, request)
    assert code == 2
    assert wire["requests"] == []
    assert not output.exists()


def test_missing_capability_falls_back_without_transmission(
    tmp_path, wire, monkeypatch, capsys
):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    code, _, output = _invoke(tmp_path, wire)
    assert code == 3
    assert wire["requests"] == []
    assert "TYPESAFE_API_KEY is absent" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize(
    "status,expected",
    [
        (400, 2),
        (422, 2),
        (401, 5),
        (403, 5),
        (408, 3),
        (429, 3),
        (500, 3),
        (503, 3),
        (404, 4),
    ],
)
def test_http_failures_preserve_meaning_without_retry(tmp_path, wire, status, expected):
    wire["status"] = status
    code, _, output = _invoke(tmp_path, wire)
    assert code == expected
    assert len(wire["requests"]) == 1
    assert not output.exists()


def test_response_read_timeout_is_unavailable_without_a_judgment(
    tmp_path, wire, monkeypatch
):
    module = _module()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            raise TimeoutError("read timeout")

    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: Response())
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    request.write_text(json.dumps(_request()))
    assert module.main(["--request", str(request), "--output", str(output)]) == 3
    assert not output.exists()


@pytest.mark.parametrize(
    "item,levels,score",
    [
        ("duplicate owner", ["duplicate responsibility", "reuses existing owner"], 0),
        ("incompatible dependency", ["consumer contract broken", "compatible"], 0),
        (
            "rollback incomplete",
            ["rollback lacks required state recovery", "complete plan"],
            0,
        ),
        ("recovery without evidence", ["unobserved claim", "observed recovery"], 0),
        (
            "no rollout justified",
            ["unjustified deployment omission", "no deployment in scope"],
            1,
        ),
        ("guarantee DNB", ["claimed observed", "explicitly designed not built"], 1),
        (
            "existing authority adequate",
            ["competing authority", "current owner authority"],
            1,
        ),
    ],
)
def test_controlled_pilot_keeps_review_units_and_response_provenance(
    tmp_path, wire, item, levels, score
):
    # This is a transport pilot with canned local judgments, NOT Jev accuracy
    # evidence. The reviewer must verify reasons independently on real sources.
    request = {
        "state": {"review_unit": item, "scope": "authorized minimized design"},
        "model": "jev-latest",
        "questions": {"assessment": {"type": "score", "criteria": levels}},
    }
    response = {
        "model": "local-controlled-not-jev",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "answers": {
            "assessment": {
                "type": "score",
                "score": score,
                "confidence": 1,
                "legend": {str(i): level for i, level in enumerate(levels)},
                "probabilities": {"0": 1 - score, "1": score},
            }
        },
        "provenance": "canned loopback response, not service inference",
    }
    wire["body"] = json.dumps(response).encode()
    code, authored, output = _invoke(tmp_path, wire, request)
    assert code == 0
    assert wire["requests"] == [authored.read_bytes()]
    assert json.loads(output.read_bytes()) == response
    assert "jev_reason" not in output.read_text()
