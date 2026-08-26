from .base import StorageBackend
from .local import LocalVolumeStorage
from .service import StorageService

__all__ = ['StorageBackend', 'LocalVolumeStorage', 'StorageService', 'get_storage_service']

def get_storage_service() -> StorageService:
    # Later this could read from config to pick Local vs S3
    import os
    # Default local directory inside docker is /data/documents or something.
    # We will use /tmp/clinextract_data for local development, or mapped volume.
    storage_dir = os.getenv("STORAGE_DIR", "/app/data/documents")
    backend = LocalVolumeStorage(base_dir=storage_dir)
    return StorageService(backend=backend)
