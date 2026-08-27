from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from core.config import settings
from services.repo_service import RepoService


@pytest.fixture
def service() -> RepoService:
    return RepoService(store=object())


@pytest.mark.parametrize(
    "member_name",
    [
        "../extracted-evil/pwn.txt",
        "../../pwn.txt",
        "/absolute/pwn.txt",
        r"..\\windows-escape\\pwn.txt",
        r"C:\\temp\\pwn.txt",
    ],
)
def test_safe_extract_rejects_unsafe_paths(
    tmp_path: Path, service: RepoService, member_name: str
) -> None:
    archive = tmp_path / "malicious.zip"
    destination = tmp_path / "extracted"
    destination.mkdir()

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(member_name, "should never be accepted")

    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(HTTPException, match="Unsafe ZIP path detected"):
            service._safe_extract(zf, destination)


def test_safe_extract_accepts_normal_members(tmp_path: Path, service: RepoService) -> None:
    archive = tmp_path / "normal.zip"
    destination = tmp_path / "extracted"
    destination.mkdir()

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("src/main.py", "print('ok')")

    with zipfile.ZipFile(archive) as zf:
        service._safe_extract(zf, destination)

    assert (destination / "src" / "main.py").read_text(encoding="utf-8") == "print('ok')"


def test_safe_extract_enforces_total_uncompressed_bound(
    tmp_path: Path, service: RepoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    archive = tmp_path / "oversized-total.zip"
    destination = tmp_path / "extracted"
    destination.mkdir()

    payload = b"x" * 600_000
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.bin", payload)
        zf.writestr("b.bin", payload)

    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(HTTPException, match="total uncompressed size"):
            service._safe_extract(zf, destination)


def test_detect_stack_handles_nested_monorepo_layout(tmp_path: Path, service: RepoService) -> None:
    files = {
        "apps/web/package.json": '{"dependencies":{"@sveltejs/kit":"^2.0.0"}}',
        "apps/web/svelte.config.js": "export default {};",
        "apps/web/vite.config.ts": "export default {};",
        "apps/api/requirements.txt": "fastapi>=0.115\nuvicorn>=0.30\n",
        "apps/api/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        "infrastructure/Dockerfile": "FROM python:3.11-slim\n",
        ".github/workflows/ci.yml": "name: ci\n",
        "deploy/vercel.json": "{}",
    }
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    repo_files = service.list_files_from_root(tmp_path)
    stack = service.detect_stack(tmp_path, repo_files)

    assert set(stack) >= {
        "Node",
        "SvelteKit",
        "Vite",
        "Python",
        "FastAPI",
        "Docker",
        "GitHub Actions",
        "Vercel",
    }
