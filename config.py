from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080
    # Default scenario when no explicit override is set
    default_scenario: str = "simple_response"
    # Delay between streamed chunks (seconds)
    chunk_delay: float = 0.05
    # Delay before the ask-user question is emitted
    ask_user_delay: float = 0.3

    model_config = {"env_prefix": "MOCK_"}


settings = Settings()
