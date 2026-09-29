"""Frontier executor connector registration and OpenCode integration."""
from __future__ import annotations

import subprocess
import textwrap
from collections.abc import Callable
from typing import Any

from agent.config import AgentConfig
from agent.providers import BaseExecutorProvider, register_harness

ConnectorFactory = Callable[[AgentConfig], BaseExecutorProvider]


def register_connector(name: str, factory: ConnectorFactory) -> None:
    """Register a Frontier executor connector with mcts-agent's plugin registry.

    Future connectors can implement BaseExecutorProvider and register using
    this function. Frontier keeps assessment orchestration independent of the
    selected execution harness.
    """
    register_harness(name, executor_factory=factory)


class OpenCodeExecutorProvider(BaseExecutorProvider):
    """Run one bounded task through OpenCode's non-interactive CLI."""

    def __init__(self, model: str = "", timeout: int = 1800, command: str = "opencode"):
        self.model = model
        self.timeout = timeout
        self.command = command

    def execute_action(self, action: str, goal: str, workspace_dir: str) -> dict[str, Any]:
        prompt = textwrap.dedent(f"""\
            Goal:
            {goal.strip()}

            Bounded task:
            {action.strip()}

            Work only in the supplied workspace. Complete the task and report actual
            observations, conclusions, artifacts, and workspace changes separately.
            Do not claim an experiment or test ran unless it actually ran.
        """)
        cmd = [self.command, "run", "--format", "json", "--dir", workspace_dir]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(prompt)
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "success": False,
                "stdout": exc.stdout or "",
                "stderr": "OpenCode execution timed out",
                "returncode": -1,
                "cancelled": True,
            }
        except OSError as exc:
            return {"success": False, "stdout": "", "stderr": str(exc), "returncode": -1}


def register() -> None:
    """Entry point loaded by mcts-agent when executor plugins are discovered."""
    register_connector(
        "opencode",
        lambda config: OpenCodeExecutorProvider(
            config.executor_model, config.executor_timeout
        ),
    )
