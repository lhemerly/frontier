from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

import pytest
from agent.config import AgentConfig

from frontier.cli import run_assessment
from frontier.connectors import OpenCodeExecutorProvider, register_connector


def test_opencode_invokes_noninteractive_cli_with_workspace_model_and_prompt(tmp_path):
    provider = OpenCodeExecutorProvider(model="provider/model", timeout=42)
    completed = CompletedProcess(
        args=["opencode"], returncode=0, stdout='{"type":"text","text":"done"}\n', stderr=""
    )
    with patch("frontier.connectors.subprocess.run", return_value=completed) as run:
        result = provider.execute_action("inspect the code", "find an issue", str(tmp_path))

    assert result["success"] is True
    assert result["returncode"] == 0
    args, kwargs = run.call_args
    assert args[0][:6] == [
        "opencode", "run", "--format", "json", "--dir", str(tmp_path)
    ]
    assert args[0][-3:] == ["--model", "provider/model", args[0][-1]]
    assert "Goal:\nfind an issue" in args[0][-1]
    assert "Bounded task:\ninspect the code" in args[0][-1]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["timeout"] == 42


def test_opencode_timeout_is_reported_as_cancelled(tmp_path):
    with patch(
        "frontier.connectors.subprocess.run",
        side_effect=TimeoutExpired("opencode", 3, output="partial"),
    ):
        result = OpenCodeExecutorProvider(timeout=3).execute_action("task", "goal", str(tmp_path))

    assert result["success"] is False
    assert result["cancelled"] is True
    assert result["returncode"] == -1
    assert result["stderr"] == "OpenCode execution timed out"


def test_opencode_missing_executable_is_reported(tmp_path):
    with patch(
        "frontier.connectors.subprocess.run",
        side_effect=FileNotFoundError("opencode not found"),
    ):
        result = OpenCodeExecutorProvider().execute_action("task", "goal", str(tmp_path))

    assert result["success"] is False
    assert result["returncode"] == -1
    assert "opencode not found" in result["stderr"]


def test_connector_registration_uses_mcts_extension_point():
    factory = lambda config: OpenCodeExecutorProvider(config.executor_model)
    with patch("frontier.connectors.register_harness") as register:
        register_connector("example", factory)
    register.assert_called_once_with("example", executor_factory=factory)


def test_new_assessment_selects_requested_connector_and_model(tmp_path, monkeypatch):
    captured = {}

    def stop_before_execution(**kwargs):
        captured.update(kwargs)
        raise RuntimeError("captured configuration")

    monkeypatch.setattr("frontier.cli.run_research", stop_before_execution)
    with pytest.raises(RuntimeError, match="captured configuration"):
        run_assessment(
            target=tmp_path,
            connector="opencode",
            model="provider/model",
            max_steps=1,
        )

    config = captured["config"]
    assert config.executor_provider == "opencode"
    assert config.executor_model == "provider/model"


def test_unknown_connector_is_rejected_before_writing_assessment(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "frontier.cli.run_research", lambda **kwargs: pytest.fail("must not execute")
    )
    with pytest.raises(ValueError, match="Unknown connector"):
        run_assessment(target=tmp_path, connector="unknown")
    assert not (tmp_path / ".frontier").exists()
