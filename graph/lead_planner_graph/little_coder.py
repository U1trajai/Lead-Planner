"""Build, validate, and run the little-coder CLI command.

The shell-safety rules that used to live as prose in the delegating skill
(checklist items 4, 5, 6) are enforced here in code: a malformed prompt is
rejected *before* anything runs, and the required flags are always appended by
the engine rather than trusted to the model. This is the heart of "offload the
fiddly control to the engine" — the LLM writes requirements; the engine
guarantees a well-formed command.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

# Characters that would be interpreted by the shell inside the double-quoted
# prompt and have historically caused failures (backticks ran the quoted word;
# a stray backslash dropped the -p flag). Parentheses, commas and apostrophes
# are safe inside double quotes and are intentionally allowed.
_FORBIDDEN = {
    "`": "backtick (the shell would execute the quoted word)",
    "$": "dollar sign (shell variable/command expansion)",
    '"': "inner double-quote (would close the prompt early)",
    "\\": "backslash (a dropped continuation breaks the flags)",
}

_ENV = "PI_RETRY_PROVIDER_TIMEOUTMS=3600000"
_REQUIRED_TAIL = ["-p", "--no-session"]


class PromptValidationError(ValueError):
    """Raised when a prompt fails the pre-send shell-safety checklist."""


@dataclass
class DelegationResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" + self.stderr if self.stderr else "")).strip()


def validate_prompt(prompt: str) -> None:
    """Enforce checklist items 4 and 5 (one physical line, no shell specials)."""
    if not prompt or not prompt.strip():
        raise PromptValidationError("prompt is empty")
    if "\n" in prompt or "\r" in prompt:
        raise PromptValidationError(
            "prompt must be a single physical line; replace newlines with sentences or semicolons"
        )
    found = sorted({c for c in _FORBIDDEN if c in prompt})
    if found:
        reasons = "; ".join(f"{c!r}: {_FORBIDDEN[c]}" for c in found)
        raise PromptValidationError(f"prompt contains forbidden shell characters -> {reasons}")


def build_command(prompt: str, *, model: str, provider: str = "lmstudio") -> str:
    """Return the validated, single-line little-coder command.

    Guarantees checklist item 6 (``-p --no-session`` always present) and that the
    env var and provider/model flags are set the same way every time.
    """
    validate_prompt(prompt)
    return (
        f'{_ENV} little-coder --provider {provider} --model {model} '
        f'"{prompt.strip()}" {" ".join(_REQUIRED_TAIL)}'
    )


def run_command(command: str, *, workdir: str, timeout: float = 3600.0) -> DelegationResult:
    """Execute the little-coder command and capture its output."""
    proc = subprocess.run(
        command,
        shell=True,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return DelegationResult(
        command=command,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def run_tests(workdir: str, *, target: str | None = None, timeout: float = 600.0) -> DelegationResult:
    """Run the component's tests with pytest — the orchestrator's job, never little-coder's.

    Uses ``sys.executable`` (the interpreter currently running the orchestrator)
    rather than a bare ``python``, which may not exist on PATH — on many systems
    only ``python3`` is present.
    """
    cmd = [sys.executable, "-m", "pytest", "-q"]
    if target:
        cmd.append(target)
    proc = subprocess.run(
        cmd,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return DelegationResult(
        command=" ".join(cmd),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
