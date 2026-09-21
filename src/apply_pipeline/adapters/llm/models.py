from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from apply_pipeline.config import Settings


def build_judge_model(settings: Settings) -> Model:
    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is required to build the judge model")

    openai_provider = OpenAIProvider(api_key=settings.openai_api_key.get_secret_value())

    primary_model = OpenAIChatModel(
        settings.openai_model,
        provider=openai_provider,
    )

    fallback_models: list[Model] = [
        OpenAIChatModel(
            settings.openai_fallback_model,
            provider=openai_provider,
        )
    ]

    if settings.anthropic_api_key is not None:
        anthropic_provider = AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value()
        )

        fallback_models.append(
            AnthropicModel(
                settings.anthropic_model,
                provider=anthropic_provider,
            )
        )

    return FallbackModel(primary_model, *fallback_models)
