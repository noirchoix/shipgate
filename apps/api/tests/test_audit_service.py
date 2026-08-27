from __future__ import annotations

from typing import Any

import pytest

from schemas.shipgate import AuditRequest
from services.audit_service import AuditService


class StubStore:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []
        self.memory_items: list[tuple[str, str, str]] = []

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        if session_id != "session-1":
            return None
        return {
            "id": session_id,
            "repo_name": "sample",
            "detected_stack": ["Python", "FastAPI"],
        }

    def save_audit(self, session_id: str, payload: dict[str, Any], score: int, readiness: str) -> None:
        self.saved.append(
            {
                "session_id": session_id,
                "payload": payload,
                "score": score,
                "readiness": readiness,
            }
        )

    def remember(self, session_id: str, key: str, value: str) -> None:
        self.memory_items.append((session_id, key, value))


class StubRepo:
    def read_targets(self, session_id: str, target_files: list[str]) -> dict[str, str]:
        return {
            ".env.example": "APP_ENV=production\n",
            "README.md": "Environment setup. Deployment instructions. Production operations.\n",
            "main.py": "from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'ok': True}\n",
            "requirements.txt": "fastapi\nuvicorn\npydantic-settings\n",
            ".github/workflows/ci.yml": "name: ci\n",
        }


@pytest.fixture
def service() -> AuditService:
    return AuditService(store=StubStore(), repo=StubRepo())


def finding_titles(findings: list[Any]) -> set[str]:
    return {finding.title for finding in findings}


def test_secret_detection_flags_token_signatures_and_public_secret_names(service: AuditService) -> None:
    files = {
        ".env.example": "APP_ENV=production\n",
        "config.ts": (
            "const github = 'ghp_" + "A" * 36 + "';\n"
            "const aws = 'AKIA" + "B" * 16 + "';\n"
            "const fine = 'github_pat_" + "C" * 30 + "';\n"
            "const exposed = import.meta.env.VITE_API_SECRET;\n"
        ),
    }

    findings = service._static_findings(files, {"repo_name": "sample"}, "auto")
    titles = finding_titles(findings)

    assert "Possible hardcoded secret detected" in titles
    assert "Potential secret exposed through public frontend environment variable" in titles


def test_secret_detection_does_not_flag_public_non_secret_url(service: AuditService) -> None:
    files = {
        ".env.example": "VITE_API_BASE_URL=http://localhost:8005\n",
        "client.ts": "const url = import.meta.env.VITE_API_BASE_URL;\n",
    }

    findings = service._static_findings(files, {"repo_name": "sample"}, "auto")

    assert "Potential secret exposed through public frontend environment variable" not in finding_titles(findings)


def test_scoring_is_order_independent_and_deterministic(service: AuditService) -> None:
    findings = [
        service._finding("blocker", "security_auditor", "b", None, "e", "w", "r"),
        service._finding("warning", "runtime_auditor", "w", None, "e", "w", "r"),
        service._finding("suggestion", "deployment_auditor", "s", None, "e", "w", "r"),
        service._finding("nit", "documentation_auditor", "n", None, "e", "w", "r"),
        service._finding("pass", "launch_plan_writer", "p", None, "e", "w", "r"),
    ]

    expected = 69
    assert service._score(findings, {}) == expected
    assert service._score(list(reversed(findings)), {}) == expected
    assert service._score(findings, {"irrelevant": "content"}) == expected


def test_llm_failure_degrades_to_static_audit(service: AuditService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_llm_mode", lambda: "deepseek")

    def fail_llm(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(service, "_llm_findings", fail_llm)

    result = service.run(AuditRequest(session_id="session-1", use_llm=True))

    fallback = [
        finding
        for finding in result["findings"]
        if finding["title"] == "LLM synthesis failed; static audit was used"
    ]
    assert len(fallback) == 1
    assert fallback[0]["severity"] == "warning"
    assert result["score"] >= 0
    assert service.store.saved


def test_offline_mode_never_calls_llm(service: AuditService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_llm_mode", lambda: "offline")

    def unexpected_llm(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("LLM must not be called in offline mode")

    monkeypatch.setattr(service, "_llm_findings", unexpected_llm)

    result = service.run(AuditRequest(session_id="session-1", use_llm=True))

    assert result["session_id"] == "session-1"
    assert "LLM synthesis failed" not in {finding["title"] for finding in result["findings"]}
