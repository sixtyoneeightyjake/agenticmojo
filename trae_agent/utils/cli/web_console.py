# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""Web CLI Console implementation using FastAPI + SSE.

This console exposes a small HTTP server with endpoints to:
- POST /api/run: trigger an Agent task execution
- GET  /api/stream: receive live Agent updates via Server-Sent Events (SSE)
- GET  /: a minimal web UI to submit tasks and view streaming updates

It integrates with the agent lifecycle through the CLIConsole interface.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from dataclasses import asdict
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from trae_agent.agent.agent_basics import AgentExecution, AgentState, AgentStep, AgentStepState
from trae_agent.tools.base import ToolCall, ToolResult
from trae_agent.utils.cli.cli_console import CLIConsole, ConsoleMode
from trae_agent.utils.config import LakeviewConfig
from trae_agent.utils.llm_clients.llm_basics import LLMResponse, LLMUsage


class RunTaskRequest(BaseModel):
    task: str
    project_path: str | None = None
    must_patch: bool | None = False
    patch_path: str | None = None


class WebCLIConsole(CLIConsole):
    """Web-based console that streams agent updates to browsers via SSE."""

    def __init__(
        self,
        mode: ConsoleMode = ConsoleMode.RUN,
        lakeview_config: LakeviewConfig | None = None,
        host: str = "127.0.0.1",
        port: int = 8000,
    ) -> None:
        super().__init__(mode, lakeview_config)
        self.app: FastAPI | None = None
        self._is_running: bool = False
        self._server: uvicorn.Server | None = None
        self.host = host
        self.port = port
        # Connected SSE clients: each gets its own queue of events
        self._clients: set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

        # Agent context for executing tasks from API
        self.agent = None
        self.config_file = None
        self.trajectory_file = None

    # ------------------- CLIConsole required methods -------------------

    async def start(self):
        """Start the FastAPI server (idempotent)."""
        if self._is_running:
            return

        self._is_running = True
        self.app = self._create_app()

        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        self._server = uvicorn.Server(config)
        try:
            await self._server.serve()
        finally:
            self._is_running = False

    def update_status(
        self, agent_step: AgentStep | None = None, agent_execution: AgentExecution | None = None
    ) -> None:
        """Broadcast updates as SSE events to all connected clients."""
        if agent_step is not None:
            event = {
                "type": "agent_step",
                "timestamp": time.time(),
                "data": self._serialize_agent_step(agent_step),
            }
            self._broadcast_event(event)

        if agent_execution is not None:
            event = {
                "type": "agent_execution",
                "timestamp": time.time(),
                "data": self._serialize_agent_execution(agent_execution),
            }
            self._broadcast_event(event)

        # Always track the latest execution for server-side summaries if needed
        if agent_execution is not None:
            self.agent_execution = agent_execution

    def print_task_details(self, details: dict[str, str]) -> None:
        event = {"type": "task_details", "timestamp": time.time(), "data": details}
        self._broadcast_event(event)

    def print(self, *objects: object, sep: str = " ") -> None:  # type: ignore[override]
        text = sep.join(str(o) for o in objects)
        event = {"type": "log", "timestamp": time.time(), "data": text}
        self._broadcast_event(event)

    def get_task_input(self) -> str | None:
        # Web console doesn't prompt in-terminal; UI collects input
        return None

    def get_working_dir_input(self) -> str:
        # For web flows we use the provided project_path; fallback to cwd
        return os.getcwd()

    def stop(self) -> None:
        if self._server and self._server.started:
            with contextlib.suppress(Exception):
                self._server.should_exit = True

    # ------------------- Public helpers -------------------

    def set_agent_context(self, agent, config_file: str | None = None, trajectory_file: str | None = None) -> None:
        """Provide the Agent so API can trigger runs."""
        self.agent = agent
        self.config_file = config_file
        self.trajectory_file = trajectory_file

    # ------------------- FastAPI app and routes -------------------

    def _create_app(self) -> FastAPI:
        app = FastAPI(title="Trae Agent Web Console")

        @app.get("/", response_class=HTMLResponse)
        async def index() -> str:
            return self._index_html()

        @app.get("/api/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/api/stream")
        async def stream() -> StreamingResponse:
            queue: asyncio.Queue[str] = asyncio.Queue()
            async with self._lock:
                self._clients.add(queue)

            async def event_gen() -> AsyncGenerator[bytes, None]:
                try:
                    while True:
                        data = await queue.get()
                        yield f"data: {data}\n\n".encode("utf-8")
                except asyncio.CancelledError:
                    # Client disconnected
                    pass
                finally:
                    async with self._lock:
                        self._clients.discard(queue)

            headers = {"Cache-Control": "no-cache", "Content-Type": "text/event-stream"}
            return StreamingResponse(event_gen(), headers=headers, media_type="text/event-stream")

        @app.post("/api/run")
        async def run_task(req: RunTaskRequest) -> JSONResponse:
            if not self.agent:
                raise HTTPException(status_code=500, detail="Agent not initialized")

            task = req.task.strip()
            if not task:
                raise HTTPException(status_code=400, detail="Task must not be empty")

            working_dir = req.project_path or os.getcwd()
            if not os.path.isabs(working_dir):
                raise HTTPException(status_code=400, detail="project_path must be absolute")

            # Prepare args consistent with CLI run
            task_args = {
                "project_path": working_dir,
                "issue": task,
                "must_patch": "true" if req.must_patch else "false",
                "patch_path": req.patch_path,
            }

            # Change working directory for execution to match CLI behavior
            prev_cwd = os.getcwd()
            try:
                os.chdir(working_dir)
                # Execute the task
                _ = await self.agent.run(task, task_args)
            finally:
                with contextlib.suppress(Exception):
                    os.chdir(prev_cwd)

            return JSONResponse({"status": "completed", "trajectory_file": getattr(self.agent, "trajectory_file", None)})

        return app

    # ------------------- Serialization helpers -------------------

    def _serialize_tool_call(self, tc: ToolCall) -> dict[str, Any]:
        return {
            "name": tc.name,
            "call_id": tc.call_id,
            "arguments": tc.arguments,
            "id": tc.id,
        }

    def _serialize_tool_result(self, tr: ToolResult) -> dict[str, Any]:
        return {
            "name": tr.name,
            "call_id": tr.call_id,
            "success": tr.success,
            "result": tr.result,
            "error": tr.error,
            "id": tr.id,
        }

    def _serialize_llm_usage(self, u: LLMUsage | None) -> dict[str, Any] | None:
        if u is None:
            return None
        return {
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0),
            "reasoning_tokens": getattr(u, "reasoning_tokens", 0),
        }

    def _serialize_llm_response(self, r: LLMResponse | None) -> dict[str, Any] | None:
        if r is None:
            return None
        return {
            "content": r.content,
            "usage": self._serialize_llm_usage(r.usage),
            "model": r.model,
            "finish_reason": r.finish_reason,
            "tool_calls": [self._serialize_tool_call(tc) for tc in (r.tool_calls or [])]
            if r.tool_calls
            else None,
        }

    def _serialize_agent_step(self, s: AgentStep) -> dict[str, Any]:
        return {
            "step_number": s.step_number,
            "state": s.state.value if isinstance(s.state, AgentStepState) else str(s.state),
            "thought": s.thought,
            "tool_calls": [self._serialize_tool_call(tc) for tc in (s.tool_calls or [])]
            if s.tool_calls
            else None,
            "tool_results": [self._serialize_tool_result(tr) for tr in (s.tool_results or [])]
            if s.tool_results
            else None,
            "llm_response": self._serialize_llm_response(s.llm_response),
            "reflection": s.reflection,
            "error": s.error,
            "extra": s.extra,
            "llm_usage": self._serialize_llm_usage(s.llm_usage),
        }

    def _serialize_agent_execution(self, e: AgentExecution) -> dict[str, Any]:
        return {
            "task": e.task,
            "steps": [self._serialize_agent_step(s) for s in e.steps],
            "final_result": e.final_result,
            "success": e.success,
            "total_tokens": self._serialize_llm_usage(e.total_tokens),
            "execution_time": e.execution_time,
            "agent_state": e.agent_state.value if isinstance(e.agent_state, AgentState) else str(e.agent_state),
        }

    def _broadcast_event(self, event: dict[str, Any]) -> None:
        try:
            data = json.dumps(event, ensure_ascii=False)
        except Exception:
            # As a fallback, attempt to serialize dataclasses
            data = json.dumps(json.loads(json.dumps(asdict(event))), ensure_ascii=False)

        # Put into all client queues without blocking
        queues = list(self._clients)
        for q in queues:
            with contextlib.suppress(Exception):
                q.put_nowait(data)

    # ------------------- UI -------------------

    def _index_html(self) -> str:
        return """
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>Trae Agent Web Console</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 0; padding: 0; background: #0b0f14; color: #e6edf3; }
    header { padding: 16px; background: #0e141b; border-bottom: 1px solid #1f2937; }
    h1 { margin: 0; font-size: 18px; }
    main { display: grid; grid-template-columns: 340px 1fr; gap: 16px; padding: 16px; }
    .card { background: #0e141b; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; }
    label { display: block; font-size: 12px; color: #94a3b8; margin: 8px 0 4px; }
    input, textarea { width: 100%; background: #0b0f14; color: #e6edf3; border: 1px solid #1f2937; padding: 8px; border-radius: 6px; }
    button { background: #2563eb; color: white; border: 0; padding: 10px 14px; border-radius: 6px; cursor: pointer; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    pre { white-space: pre-wrap; background: #0b0f14; border: 1px solid #1f2937; padding: 12px; border-radius: 6px; max-height: 70vh; overflow: auto; }
    .muted { color: #94a3b8; font-size: 12px; }
  </style>
</head>
<body>
  <header>
    <h1>Trae Agent Web Console</h1>
  </header>
  <main>
    <section class=\"card\">
      <form id=\"runForm\">
        <label>Task</label>
        <textarea id=\"task\" rows=\"4\" placeholder=\"Describe your coding task...\"></textarea>
        <label>Project Path (absolute)</label>
        <input id=\"project_path\" type=\"text\" placeholder=\"/absolute/path/to/project\" />
        <div style=\"margin-top:12px; display:flex; gap:8px;\">
          <button type=\"submit\" id=\"runBtn\">Run Task</button>
          <span id=\"status\" class=\"muted\"></span>
        </div>
      </form>
    </section>
    <section class=\"card\">
      <h3 style=\"margin-top:0\">Live Stream</h3>
      <pre id=\"output\">Waiting for events...</pre>
    </section>
  </main>
<script>
  const output = document.getElementById('output');
  const status = document.getElementById('status');
  const evt = new EventSource('/api/stream');
  evt.onmessage = (e) => {
    try {
      const obj = JSON.parse(e.data);
      const time = new Date(obj.timestamp * 1000).toLocaleTimeString();
      output.textContent += `\n[${time}] ${obj.type}:\n${JSON.stringify(obj.data, null, 2)}\n`;
    } catch (err) {
      output.textContent += `\n(event) ${e.data}\n`;
    }
    output.scrollTop = output.scrollHeight;
  };
  evt.onerror = () => { status.textContent = 'Disconnected from stream. Retrying...'; };
  evt.onopen = () => { status.textContent = 'Connected'; };

  document.getElementById('runForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('runBtn');
    btn.disabled = true;
    status.textContent = 'Running...';
    const task = document.getElementById('task').value;
    const project_path = document.getElementById('project_path').value;
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, project_path })
      });
      const body = await res.json();
      status.textContent = 'Completed';
      output.textContent += `\n[web] POST /api/run -> ${JSON.stringify(body)}\n`;
    } catch (err) {
      status.textContent = 'Error';
      output.textContent += `\n[error] ${err}\n`;
    } finally {
      btn.disabled = false;
    }
  });
</script>
</body>
</html>
"""