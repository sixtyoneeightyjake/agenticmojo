from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from pathlib import Path
import subprocess

from trae_agent.agent.agent_basics import AgentExecution, AgentState, AgentStep, AgentStepState
from trae_agent.tools.base import ToolCall
from trae_agent.utils.cli.cli_console import CLIConsole, ConsoleMode
from trae_agent.utils.config import LakeviewConfig


class ApiConsole(CLIConsole):
    """Console that funnels agent updates into per-run subscriber queues.

    It keeps a set of asyncio.Queue[str] subscribers and broadcasts JSON
    events compatible with the frontend RunEvent union described in SPEC.md.
    """

    def __init__(
        self,
        *,
        subscribers: set[asyncio.Queue[str]],
        mode: ConsoleMode = ConsoleMode.RUN,
        lakeview_config: LakeviewConfig | None = None,
    ) -> None:
        super().__init__(mode, lakeview_config)
        self._subs = subscribers
        self._lock = asyncio.Lock()
        self._run_state: str = "queued"
        self._repo_path: Path | None = None
        self._baseline: str | None = None
        self._last_patch: str | None = None

    async def start(self):
        # No UI to drive; just waits until execution ends.
        while self.agent_execution is None or (
            self.agent_execution.agent_state not in (AgentState.COMPLETED, AgentState.ERROR)
        ):
            await asyncio.sleep(0.5)

    def _broadcast(self, obj: dict[str, Any]) -> None:
        obj.setdefault("ts", time.time())
        data = json.dumps(obj, ensure_ascii=False)
        # snapshot to avoid mutation during iteration
        for q in list(self._subs):
            try:
                q.put_nowait(data)
            except Exception:
                # best-effort
                pass

    def update_status(
        self, agent_step: AgentStep | None = None, agent_execution: AgentExecution | None = None
    ) -> None:
        # Transition to running on first callback
        if self._run_state == "queued":
            self._run_state = "running"
            self._broadcast({"type": "status", "state": "running", "runId": ""})

        if agent_step is not None:
            tool_name = None
            if agent_step.tool_calls:
                # take first tool name for summary
                tc: ToolCall = agent_step.tool_calls[0]
                tool_name = tc.name
            summary = agent_step.llm_response.content if agent_step.llm_response else ""
            self._broadcast(
                {
                    "type": "step",
                    "index": agent_step.step_number,
                    "tool": tool_name or "unknown",
                    "summary": summary or agent_step.state.value,
                }
            )

            # Emit diff changes if repo configured
            if self._repo_path and agent_step.state in (AgentStepState.COMPLETED, AgentStepState.ERROR):
                patch = self._current_patch()
                if patch and patch != self._last_patch:
                    files = self._parse_patch(patch)
                    if files:
                        self._broadcast({"type": "diff", "files": files})
                    self._last_patch = patch

        if agent_execution is not None:
            self.agent_execution = agent_execution
            if agent_execution.agent_state in (AgentState.COMPLETED, AgentState.ERROR):
                self._run_state = "done" if agent_execution.agent_state == AgentState.COMPLETED else "error"
                self._broadcast(
                    {
                        "type": "status",
                        "state": "done" if self._run_state == "done" else "error",
                        "message": agent_execution.final_result or "",
                    }
                )

                # Emit simple metrics
                try:
                    total = len(agent_execution.steps)
                    completed = sum(1 for s in agent_execution.steps if s.state == AgentStepState.COMPLETED)
                    coverage = int(round((completed / total) * 100)) if total else 0
                    changed = self._changed_files_count()
                    combo = total
                    self._broadcast(
                        {"type": "metrics", "coverage": coverage, "refactor": changed, "combo": combo}
                    )
                except Exception:
                    pass

    def print_task_details(self, details: dict[str, str]) -> None:
        # Emit as initial log for context
        self._broadcast({"type": "output", "tool": "system", "text": json.dumps(details, indent=2)})

    def print(self, message: str, color: str = "blue", bold: bool = False):
        self._broadcast({"type": "output", "tool": "console", "text": str(message)})

    def get_task_input(self) -> str | None:
        return None

    def get_working_dir_input(self) -> str:
        return ""

    def stop(self):
        pass

    # ---------------- repo / diffs / metrics helpers ----------------
    def set_repo(self, repo_path: str, baseline: str | None = None) -> None:
        self._repo_path = Path(repo_path)
        self._baseline = baseline

    def _git(self, *args: str) -> str:
        if not self._repo_path:
            return ""
        try:
            out = subprocess.check_output(["git", "--no-pager", *args], cwd=str(self._repo_path))
            return out.decode("utf-8", "replace")
        except Exception:
            return ""

    def _current_patch(self) -> str:
        if not self._repo_path:
            return ""
        if self._baseline:
            return self._git("diff", self._baseline)
        return self._git("diff")

    def _parse_patch(self, patch: str) -> list[dict[str, str]]:
        files: list[dict[str, str]] = []
        if not patch:
            return files
        lines = patch.splitlines(True)
        current_path = None
        buf: list[str] = []
        for line in lines:
            if line.startswith("diff --git "):
                # flush previous
                if current_path is not None:
                    files.append({"path": current_path, "patch": "".join(buf)})
                # parse path
                try:
                    parts = line.strip().split()
                    a = parts[2]
                    b = parts[3]
                    path = b[2:] if b.startswith("b/") else b
                except Exception:
                    path = "unknown"
                current_path = path
                buf = [line]
            else:
                buf.append(line)
        if current_path is not None:
            files.append({"path": current_path, "patch": "".join(buf)})
        # Fallback: if we never found a header, put as a single pseudo file
        if not files:
            files = [{"path": "workspace", "patch": patch}]
        return files

    def _changed_files_count(self) -> int:
        if not self._repo_path:
            return 0
        if self._baseline:
            names = self._git("diff", "--name-only", self._baseline)
        else:
            names = self._git("diff", "--name-only")
        return len([n for n in names.splitlines() if n.strip()])
