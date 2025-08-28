from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
import contextlib
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from trae_agent.agent.agent import Agent
from trae_agent.utils.cli.cli_console import ConsoleMode
from trae_agent.utils.config import Config

from .api_console import ApiConsole


DATA_DIR = Path(os.getenv("AGENTMOJO_DATA_DIR", Path(tempfile.gettempdir()) / "agent_mojo"))
RUNS_DIR = DATA_DIR / "runs"
UPLOADS_DIR = DATA_DIR / "uploads"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class P1RunRequest(BaseModel):
    git_url: str | None = None
    zip_token: str | None = None
    tasks: list[str] | None = None
    env: dict[str, str] | None = None


class P2SessionRequest(BaseModel):
    appName: str
    description: str
    git_url: str | None = None
    zip_token: str | None = None


@dataclass
class Run:
    run_id: str
    workdir: Path
    repo_path: Path | None = None
    baseline: str | None = None
    subscribers: set[asyncio.Queue[str]] = field(default_factory=set)
    task: asyncio.Task | None = None


class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._lock = asyncio.Lock()

    async def create_run(self, payload: P1RunRequest) -> Run:
        run_id = _gen_id("run")
        workdir = RUNS_DIR / run_id
        workdir.mkdir(parents=True, exist_ok=True)

        # hydrate working copy
        if payload.git_url:
            await self._clone_repo(payload.git_url, workdir)
        elif payload.zip_token:
            await self._unpack_zip(payload.zip_token, workdir)
        else:
            # Create an empty working repo directory so the agent has a place to work
            (workdir / "repo").mkdir(parents=True, exist_ok=True)

        # Ensure a git repo exists with a baseline commit for diffs/metrics
        repo_path = workdir / "repo"
        baseline = await self._ensure_git_repo(repo_path)

        # Prepare console and agent
        subs: set[asyncio.Queue[str]] = set()
        console = ApiConsole(subscribers=subs, mode=ConsoleMode.RUN)
        if hasattr(console, "set_repo"):
            console.set_repo(str(repo_path), baseline)

        config_file = os.getenv("TRAE_CONFIG_FILE", "trae_config.yaml")
        config = Config.create(config_file=config_file).resolve_config_values()
        agent = Agent("trae_agent", config, cli_console=console)

        # Compose task text
        task_text = "\n".join(payload.tasks or ["Run repository checks and patch as needed."])

        async def runner():
            extra = {
                "project_path": str(repo_path.resolve()),
                "issue": task_text,
                "must_patch": "false",
            }
            try:
                await agent.run(task_text, extra)
            except Exception as e:
                # Push a final error event for listeners
                event = json.dumps({"type": "error", "message": str(e)})
                for q in list(subs):
                    with contextlib.suppress(Exception):
                        q.put_nowait(event)

        t = asyncio.create_task(runner())
        run = Run(run_id=run_id, workdir=workdir, repo_path=repo_path, baseline=baseline, subscribers=subs, task=t)
        async with self._lock:
            self._runs[run_id] = run
        return run

    async def attach(self, run_id: str) -> asyncio.Queue[str]:
        async with self._lock:
            run = self._runs.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        q: asyncio.Queue[str] = asyncio.Queue()
        run.subscribers.add(q)
        return q

    async def _clone_repo(self, git_url: str, dest: Path) -> None:
        import subprocess

        repo_path = dest / "repo"
        cmd = ["git", "clone", "--depth", "1", git_url, str(repo_path)]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=400, detail=f"git clone failed: {e}")

    async def _unpack_zip(self, token: str, dest: Path) -> None:
        import zipfile

        zip_path = UPLOADS_DIR / f"{token}.zip"
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="zip token not found")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest / "repo")

    async def _ensure_git_repo(self, repo_path: Path) -> str | None:
        """Ensure repo_path is a git repository with a baseline commit; return baseline sha or None."""
        import subprocess
        repo_path.mkdir(parents=True, exist_ok=True)
        try:
            if not (repo_path / ".git").exists():
                subprocess.check_call(["git", "init"], cwd=str(repo_path))
                subprocess.check_call(["git", "config", "user.email", "bot@example.local"], cwd=str(repo_path))
                subprocess.check_call(["git", "config", "user.name", "Agent Mojo"], cwd=str(repo_path))
                subprocess.check_call(["git", "add", "-A"], cwd=str(repo_path))
                subprocess.check_call(["git", "commit", "-m", "baseline"], cwd=str(repo_path))
            else:
                # Create a baseline commit if repo has none
                res = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=str(repo_path), capture_output=True)
                if res.returncode != 0:
                    subprocess.check_call(["git", "add", "-A"], cwd=str(repo_path))
                    subprocess.check_call(["git", "commit", "-m", "baseline"], cwd=str(repo_path))
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo_path)).decode().strip()
            return sha
        except Exception:
            return None


RUNS = RunManager()


class Session:
    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.sockets: set[WebSocket] = set()
        self.pending_text: str | None = None


SESSIONS: dict[str, Session] = {}


app = FastAPI(title="Agent Mojo API")


@app.post("/api/p1/run")
async def p1_start(payload: P1RunRequest) -> dict[str, str]:
    run = await RUNS.create_run(payload)
    return {"run_id": run.run_id}


@app.get("/api/p1/stream/{run_id}")
async def p1_stream(run_id: str) -> StreamingResponse:
    q = await RUNS.attach(run_id)

    async def gen() -> AsyncGenerator[bytes, None]:
        try:
            while True:
                item = await q.get()
                yield f"data: {item}\n\n".encode("utf-8")
        except asyncio.CancelledError:
            pass

    headers = {"Cache-Control": "no-cache", "Content-Type": "text/event-stream"}
    return StreamingResponse(gen(), headers=headers, media_type="text/event-stream")


@app.post("/api/p2/session")
async def p2_session(req: P2SessionRequest) -> dict[str, str]:
    session_id = _gen_id("s")
    SESSIONS[session_id] = Session(session_id)
    return {"session_id": session_id}


@app.websocket("/api/p2/ws/{session_id}")
async def p2_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    session = SESSIONS.get(session_id)
    if not session:
        await ws.close(code=1008)
        return
    session.sockets.add(ws)
    try:
        await ws.send_text(json.dumps({"role": "system", "text": "Connected."}))
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                msg = {"type": "answer", "text": data}

            # Very minimal interactive logic
            if msg.get("type") == "answer":
                await ws.send_text(
                    json.dumps(
                        {
                            "role": "assistant",
                            "text": f"Received. Would you like me to run: {msg.get('text')}?",
                            "type": "proposal",
                            "actions": [
                                {"id": "run_now", "summary": "Run requested task in 1P mode"}
                            ],
                        }
                    )
                )
                session.pending_text = msg.get("text")
            elif msg.get("type") == "approve" and msg.get("actionId") == "run_now":
                await ws.send_text(json.dumps({"role": "assistant", "text": "Running…"}))
                # Start a background run and forward events into the chat as output messages
                payload = P1RunRequest(tasks=[session.pending_text or ""], git_url=None, zip_token=None)
                run = await RUNS.create_run(payload)
                q = await RUNS.attach(run.run_id)

                async def forward():
                    try:
                        while True:
                            item = await q.get()
                            try:
                                obj = json.loads(item)
                            except Exception:
                                obj = {"type": "output", "text": item}
                            # Minimal mapping to chat messages
                            if obj.get("type") == "output":
                                await ws.send_text(json.dumps({"role": "assistant", "text": obj.get("text", "")}))
                            elif obj.get("type") == "step":
                                await ws.send_text(json.dumps({"role": "assistant", "text": f"Step {obj.get('index')}: {obj.get('tool')} — {obj.get('summary')}"}))
                            elif obj.get("type") == "status" and obj.get("state") in ("done", "error"):
                                await ws.send_text(json.dumps({"role": "assistant", "text": f"Run {obj.get('state')}"}))
                                break
                    except asyncio.CancelledError:
                        pass

                asyncio.create_task(forward())
            elif msg.get("type") == "reject":
                await ws.send_text(json.dumps({"role": "assistant", "text": "Ok, skipping."}))
            else:
                await ws.send_text(json.dumps({"role": "assistant", "text": "Noted."}))
    except WebSocketDisconnect:
        pass
    finally:
        with contextlib.suppress(Exception):
            session.sockets.discard(ws)


@app.post("/api/upload")
async def upload_zip(file: UploadFile) -> dict[str, str]:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail=".zip file required")
    token = uuid.uuid4().hex[:12]
    dest = UPLOADS_DIR / f"{token}.zip"
    data = await file.read()
    dest.write_bytes(data)
    return {"zip_token": token}


# After API routes, optionally mount built frontend at root
FRONTEND_DIST = (Path(__file__).resolve().parents[1] / "frontend" / "dist")
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


def main():
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
