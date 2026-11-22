import logging
from typing import Optional

from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger("uvicorn.error")


class OpenAIServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def require_openai_api_key() -> str:
    api_key = settings.OPENAI_API_KEY
    if not api_key or not api_key.startswith("sk-") or api_key.startswith("sk-proj-your"):
        raise OpenAIServiceError("백엔드 OPENAI_API_KEY 설정이 필요합니다.", status_code=503)
    return api_key


def create_chat_model(temperature: float = 0.2) -> ChatOpenAI:
    api_key = require_openai_api_key()
    model = settings.OPENAI_MODEL
    if not model:
        raise OpenAIServiceError("백엔드 OPENAI_MODEL 설정이 비어 있습니다.", status_code=503)
    # GPT-5/6 API models currently accept only the default temperature value.
    # Omitting it lets the API apply that default while retaining lower temperatures
    # for model families that support tuning.
    model_options = {} if model.startswith(("gpt-5", "gpt-6")) else {"temperature": temperature}
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        timeout=30,
        max_retries=0,
        **model_options,
    )


def public_openai_error(error: Exception, action: str) -> OpenAIServiceError:
    """Convert provider/parser exceptions into safe, actionable messages without echoing request data."""
    status: Optional[int] = getattr(error, "status_code", None)
    code = str(getattr(error, "code", "") or "").lower()
    param = str(getattr(error, "param", "") or "").lower()
    error_name = type(error).__name__.lower()

    if code in {"insufficient_quota", "billing_hard_limit_reached", "credit_balance_exhausted"}:
        return OpenAIServiceError("OpenAI 사용 한도 또는 결제 잔액을 확인해 주세요.", 503)
    if status == 401:
        return OpenAIServiceError("OpenAI API 키 인증에 실패했습니다. 백엔드 키 설정을 확인해 주세요.", 503)
    if status == 403:
        return OpenAIServiceError("OpenAI 프로젝트의 모델 사용 권한을 확인해 주세요.", 503)
    if status == 404 or code in {"model_not_found", "not_found"} or param == "model":
        model_setting = "OPENAI_EMBEDDING_MODEL" if "임베딩" in action else "OPENAI_MODEL"
        return OpenAIServiceError(
            f"{model_setting}이 OpenAI API에서 지원되는 모델인지 확인해 주세요.", 503
        )
    if status == 429:
        return OpenAIServiceError("OpenAI 요청 한도에 도달했습니다. 잠시 후 사용량 한도를 확인해 주세요.", 503)
    if status == 400:
        return OpenAIServiceError(
            f"{action} 요청 또는 구조화 출력 스키마를 OpenAI가 거부했습니다. 모델과 스키마 설정을 확인해 주세요.",
            502,
        )
    if "timeout" in error_name:
        return OpenAIServiceError(f"{action} 요청 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.", 504)
    if "connection" in error_name:
        return OpenAIServiceError(f"{action} 중 OpenAI 네트워크 연결에 실패했습니다.", 502)
    if "validation" in error_name or "parser" in error_name or "outputparse" in error_name:
        return OpenAIServiceError(f"{action} 응답이 지정된 구조화 형식과 일치하지 않습니다.", 502)
    return OpenAIServiceError(f"{action}에 실패했습니다. OpenAI 설정과 API 상태를 확인해 주세요.", 502)


def log_token_usage(response, action: str) -> None:
    """Log counts only when the provider returns them; never log prompts or responses."""
    usage = getattr(response, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is None and output_tokens is None:
        return
    logger.info(
        "OpenAI usage action=%s model=%s input_tokens=%s output_tokens=%s",
        action,
        settings.OPENAI_MODEL,
        input_tokens,
        output_tokens,
    )
