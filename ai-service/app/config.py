"""Application configuration placeholder."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "WattWise AI Service"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0

    mcp_server_path: str = "mcp_server/server.py"
    node_backend_url: str = "http://localhost:5000"
    ai_service_internal_token: str = ""

    class Config:
        env_file = ".env"


settings = Settings()