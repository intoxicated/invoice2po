"""
LangChain model factory for easy model switching.
Configure via env: LLM_PROVIDER (anthropic|openai|google), LLM_MODEL (model name).
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """
    Return a LangChain ChatModel based on LLM_PROVIDER and LLM_MODEL.
    Default: google / gemini-3-flash-preview
    """
    provider = (os.environ.get("LLM_PROVIDER") or "google").lower()
    model_name = os.environ.get("LLM_MODEL") or _default_model(provider)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            max_tokens=8192,
            temperature=0,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            max_tokens=8192,
            temperature=0,
        )
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            max_output_tokens=8192,
            temperature=0,
        )
    if provider == "perplexity":
        from langchain_perplexity import ChatPerplexity

        return ChatPerplexity(
            model=model_name,
            max_tokens=8192,
            temperature=0,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Use anthropic, openai, or google.")


def _default_model(provider: str) -> str:
    defaults = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
        "google": "gemini-3-flash-preview",
    }
    return defaults.get(provider, "claude-sonnet-4-20250514")
