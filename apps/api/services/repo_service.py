from __future__ import annotations
import os, shutil, uuid, zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from fastapi import UploadFile, HTTPException
from core.config import settings
from repositories.store import Store
from schemas.shipgate import RepoFile

TEXT_SUFFIXES = {'.py','.ts','.tsx','.js','.jsx','.svelte','.json','.md','.txt','.yml','.yaml','.toml','.env','.example','.css','.html','.sh','.sql','.ini','.cfg','.conf','.dockerfile'}
DEFAULT_PATTERNS = ['readme','package.json','requirements.txt','pyproject.toml','vite.config','svelte.config','app.html','client.ts','main.py','router','schema','service','.env.example','dockerfile','docker-compose','vercel.json','render.yaml','railway','procfile','.github/workflows']

class RepoService:
    def __init__(self, store: Store):
        self.store = store

    def _safe_extract(self, zf: zipfile.ZipFile, dest: Path):
        dest = dest.resolve()
        max_bytes = settings.max_upload_mb * 1024 * 1024
        total_uncompressed = 0

        for member in zf.infolist():
            normalized = member.filename.replace('\\', '/')
            member_path = PurePosixPath(normalized)
            first_part = member_path.parts[0] if member_path.parts else ''

            if (
                member_path.is_absolute()
                or '..' in member_path.parts
                or first_part.endswith(':')
            ):
                raise HTTPException(400, 'Unsafe ZIP path detected')

            target = (dest / Path(*member_path.parts)).resolve()
            try:
                target.relative_to(dest)
            except ValueError:
                raise HTTPException(400, 'Unsafe ZIP path detected')

            if member.file_size > max_bytes:
                raise HTTPException(400, f'ZIP member too large: {member.filename}')

            total_uncompressed += member.file_size
            if total_uncompressed > max_bytes:
                raise HTTPException(
                    400,
                    f'ZIP total uncompressed size exceeds {settings.max_upload_mb}MB'
                )

        zf.extractall(dest)

    async def upload(self, file: UploadFile):
        if not file.filename or not file.filename.lower().endswith('.zip'):
            raise HTTPException(400, 'Upload a .zip repository archive')
        sid = uuid.uuid4().hex[:12]
        upload_dir = settings.uploads_path / sid
        upload_dir.mkdir(parents=True, exist_ok=True)
        zip_path = upload_dir / 'repo.zip'
        raw = await file.read()
        if len(raw) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(400, f'Max upload size is {settings.max_upload_mb}MB')
        zip_path.write_bytes(raw)
        extract_dir = upload_dir / 'extracted'
        extract_dir.mkdir(exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(400, 'Invalid ZIP archive')
        root = self._repo_root(extract_dir)
        files = self.list_files_from_root(root)
        stack = self.detect_stack(root, files)
        defaults = self.default_targets(files)
        self.store.create_session(session_id=sid, repo_name=root.name, upload_path=str(zip_path), extracted_path=str(root), detected_stack=stack, file_count=len(files))
        return {'session_id': sid, 'repo_name': root.name, 'file_count': len(files), 'detected_stack': stack, 'default_targets': defaults}

    def _repo_root(self, extract_dir: Path) -> Path:
        children = [p for p in extract_dir.iterdir() if p.name not in {'__MACOSX'}]
        dirs = [p for p in children if p.is_dir()]
        files = [p for p in children if p.is_file()]
        if len(dirs) == 1 and not files:
            return dirs[0]
        return extract_dir

    def list_files(self, session_id: str) -> list[RepoFile]:
        session = self.store.get_session(session_id)
        if not session: raise HTTPException(404, 'Session not found')
        return self.list_files_from_root(Path(session['extracted_path']))

    def list_files_from_root(self, root: Path) -> list[RepoFile]:
        out=[]
        skip_dirs={'.git','node_modules','.venv','venv','dist','build','.svelte-kit','__pycache__','.next','.pytest_cache'}
        for p in root.rglob('*'):
            if not p.is_file(): continue
            if any(part in skip_dirs for part in p.relative_to(root).parts): continue
            rel = p.relative_to(root).as_posix()
            if p.stat().st_size > 512_000: continue
            kind = self.kind(rel)
            out.append(RepoFile(path=rel, size=p.stat().st_size, kind=kind))
        return sorted(out, key=lambda f: f.path.lower())

    def kind(self, path: str) -> str:
        low=path.lower(); name=Path(low).name
        if name in {'package.json','vite.config.ts','svelte.config.js','svelte.config.ts'}: return 'frontend-config'
        if name in {'requirements.txt','pyproject.toml','main.py'} or '/routers/' in low or '/services/' in low: return 'backend-config'
        if '.github/workflows/' in low: return 'ci-cd'
        if name in {'dockerfile','docker-compose.yml','vercel.json','render.yaml','railway.json','procfile'}: return 'deployment'
        if '.env' in name: return 'environment'
        if name.endswith('.md'): return 'documentation'
        return Path(path).suffix.lower().lstrip('.') or 'file'

    def detect_stack(self, root: Path, files: list[RepoFile]) -> list[str]:
        paths = {f.path.lower() for f in files}
        basenames = {PurePosixPath(p).name for p in paths}
        stack = []

        if 'package.json' in basenames:
            stack.append('Node')
        if any('svelte.config' in p for p in paths):
            stack.append('SvelteKit')
        if any(p.endswith(('vite.config.ts', 'vite.config.js')) for p in paths):
            stack.append('Vite')
        if {'requirements.txt', 'pyproject.toml'} & basenames:
            stack.append('Python')

        fastapi_detected = any(
            'routers' in PurePosixPath(p).parts for p in paths
        )
        if not fastapi_detected:
            for repo_file in files:
                name = PurePosixPath(repo_file.path.lower()).name
                if name not in {'requirements.txt', 'pyproject.toml', 'main.py'}:
                    continue
                path = root / repo_file.path
                try:
                    text = path.read_text(encoding='utf-8', errors='ignore')[:64_000].lower()
                except OSError:
                    continue
                if 'fastapi' in text:
                    fastapi_detected = True
                    break
        if fastapi_detected:
            stack.append('FastAPI')

        if 'dockerfile' in basenames:
            stack.append('Docker')
        if any('.github/workflows/' in p for p in paths):
            stack.append('GitHub Actions')
        if 'vercel.json' in basenames:
            stack.append('Vercel')
        return stack or ['Unknown']

    def default_targets(self, files: list[RepoFile]) -> list[str]:
        selected=[]
        for f in files:
            low=f.path.lower()
            if any(p in low for p in DEFAULT_PATTERNS): selected.append(f.path)
        return selected[:80]

    def read_targets(self, session_id: str, target_files: list[str]) -> dict[str,str]:
        session=self.store.get_session(session_id)
        if not session: raise HTTPException(404, 'Session not found')
        root=Path(session['extracted_path']).resolve()
        all_files={f.path for f in self.list_files_from_root(root)}
        if not target_files:
            target_files=self.default_targets(self.list_files_from_root(root))
        content={}
        for rel in target_files:
            if rel not in all_files: continue
            p=(root/rel).resolve()
            if not str(p).startswith(str(root)): continue
            try:
                content[rel]=p.read_text(encoding='utf-8', errors='ignore')[:16000]
            except Exception:
                pass
        return content
