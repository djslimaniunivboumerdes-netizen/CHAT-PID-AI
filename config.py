import os
from pydantic import BaseModel

class Settings(BaseModel):
    # Application Config
    APP_NAME: str = "pid_ai"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Storage Paths
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")
    EXPORT_DIR: str = os.path.join(BASE_DIR, "exports")
    SAMPLE_DIR: str = os.path.join(BASE_DIR, "sample_data")
    STATIC_DIR: str = os.path.join(BASE_DIR, "static")

    # Database Configuration (Defaults to SQLite for 100% free zero-config deployment)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./pid_ai.db")

    # AI Model Configuration
    YOLO_MODEL_PATH: str = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Initialize settings singleton
settings = Settings()

# Ensure required directories exist
for directory in [settings.UPLOAD_DIR, settings.EXPORT_DIR, settings.SAMPLE_DIR, settings.STATIC_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
