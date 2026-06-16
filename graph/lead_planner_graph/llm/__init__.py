"""Pluggable LLM layer.

The top of this package is the adapters themselves, one per file:

  lmstudio.py — LMStudioAdapter (local LM Studio OpenAI-compatible server)
  fake.py     — FakeLLM (deterministic, for tests and ``run.py --demo``)

The contract they implement (the ``LLM`` Protocol) and the shared output-parsing
helper (``extract_json_block``) live in ``framework/``. Add a provider by
dropping a new module here whose class has a ``complete(system, user) -> str``
method — nothing imports it except whoever constructs it (run.py / app.py).

The public surface (``LLM``, ``LMStudioAdapter``, ``extract_json_block``) is
unchanged, so existing ``from ...llm import X`` imports keep working.
"""

from .fake import FakeLLM
from .framework import LLM, extract_json_block
from .lmstudio import LMStudioAdapter

__all__ = ["LLM", "extract_json_block", "LMStudioAdapter", "FakeLLM"]
