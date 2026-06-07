from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./ontoprompt.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-key"
    encryption_key: str = ""
    first_admin_user: str = "admin"
    first_admin_password: str = "changeme123"
    uploads_dir: str = "./uploads"
    access_token_expire_minutes: int = 1440  # 24h

    # v2 — Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ontoprompt123"

    # v2 — MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_use_ssl: bool = False

    # v2 — ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    model_config = {"env_file": ".env"}

settings = Settings()
