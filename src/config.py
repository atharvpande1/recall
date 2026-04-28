from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    GEMINI_API_KEY: str
    YOUTUBE_TRANSCRIPT_API_KEY: str
    
    
app_settings = AppSettings()