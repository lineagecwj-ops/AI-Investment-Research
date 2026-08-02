from dataclasses import dataclass
import os


DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_MAX_OUTPUT_TOKENS = 2400
DEFAULT_REASONING_EFFORT = "minimal"
DEFAULT_TEXT_VERBOSITY = "low"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_RESEARCH_QUESTION_LENGTH = 1500


@dataclass(frozen=True)
class AIResearchConfig:
    model: str
    max_output_tokens: int
    reasoning_effort: str
    text_verbosity: str
    timeout_seconds: float


def get_ai_research_config() -> AIResearchConfig:
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
    if not model:
        model = DEFAULT_OPENAI_MODEL

    return AIResearchConfig(
        model=model,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        reasoning_effort=DEFAULT_REASONING_EFFORT,
        text_verbosity=DEFAULT_TEXT_VERBOSITY,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )
