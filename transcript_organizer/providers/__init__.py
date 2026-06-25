from .base import Provider, MockProvider


def get_provider(config) -> Provider:
    name = config.provider
    if name == "mock":
        return MockProvider()
    if name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(config.providers["gemini"])
    if name == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(config.providers["anthropic"])
    if name == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(config.providers["openai"])
    if name == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(config.providers["ollama"])
    raise ValueError(f"unknown provider: {name}")
