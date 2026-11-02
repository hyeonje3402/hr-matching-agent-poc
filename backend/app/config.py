import os
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


class Settings:
    PROJECT_NAME: str = "B2B HR 채용 매칭 에이전트 API"
    VERSION: str = "1.0.0"

    @property
    def OPENAI_API_KEY(self) -> str:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        return os.getenv("OPENAI_API_KEY", "").strip()

    @property
    def OPENAI_MODEL(self) -> str:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    @property
    def EMBEDDING_MODEL(self) -> str:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip()

    @property
    def CHROMA_PERSIST_DIR(self) -> str:
        return os.getenv("CHROMA_PERSIST_DIR", "./chroma_db").strip()


settings = Settings()

