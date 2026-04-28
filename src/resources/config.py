from src.config import AppSettings


class ResourcesSettings(AppSettings):
    
    
    YOUTUBE_TRANSCRIPT_API_URL: str = "https://www.youtube-transcript.io/api/transcripts"
    
    YOUTUBE_PLAYLIST_MAX_ITEMS: int = 50
    YOUTUBE_PLAYLIST_MAX_ITEMS: int = 10
    
    
    
    
    
resources_settings = ResourcesSettings()