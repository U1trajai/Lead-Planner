"""The LLM framework — the contract adapters implement plus shared parsing.

``LLM`` is the Protocol; ``extract_json_block`` reads the JSON output contract
from a reply. Depends on nothing but stdlib, and never on an adapter module —
the dependency runs one way: adapters/consumers -> framework.
"""

from .base import LLM
from .parsing import extract_json_block

__all__ = ["LLM", "extract_json_block"]
