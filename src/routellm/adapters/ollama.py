"""Adapter for Ollama's OpenAI-compatible local API."""

from routellm.adapters.openai_compatible import OpenAICompatibleInferenceAdapter


class OllamaInferenceAdapter(OpenAICompatibleInferenceAdapter):
    """Calls an Ollama server through its `/v1/chat/completions` compatibility endpoint."""
