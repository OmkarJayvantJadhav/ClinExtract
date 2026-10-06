from .base import StorageBackend
from .local import LocalVolumeStorage
from .service import StorageService

__all__ = ['StorageBackend', 'LocalVolumeStorage', 'StorageService', 'get_storage_service']

def get_storage_service() -> StorageService:
    import os
    from src.core.config import settings
    # Mapped Docker volume by default; override with STORAGE_DIR for local development.
    storage_dir = os.getenv("STORAGE_DIR", "/app/data/documents")
    backend = LocalVolumeStorage(base_dir=storage_dir, encryption_key=settings.DOCUMENT_ENCRYPTION_KEY)
    return StorageService(backend=backend)
