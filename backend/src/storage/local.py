import os
import aiofiles
import typing
from .base import StorageBackend

class LocalVolumeStorage(StorageBackend):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    async def upload_file(self, key: str, file_stream: typing.BinaryIO) -> str:
        file_path = self._safe_path(key)
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := file_stream.read(8192):
                await f.write(chunk)
        return file_path

    async def upload_artifact(self, key: str, data: str) -> str:
        # Saved next to the documents directory, e.g. /app/data/artifacts (mounted as its own volume)
        artifacts_dir = os.path.join(os.path.dirname(self.base_dir), 'artifacts')
        os.makedirs(artifacts_dir, exist_ok=True)
        file_path = os.path.join(artifacts_dir, key)
        temp_path = file_path + ".tmp"
        
        try:
            async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
                await f.write(data)
                
            os.replace(temp_path, file_path)  # os.replace is atomic and replaces if exists
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
            
        return file_path

    def _safe_path(self, key: str) -> str:
        # Keys are generated UUIDs; refuse anything that could escape the storage directory.
        if not key or os.path.basename(key) != key or key in (".", ".."):
            raise ValueError(f"Invalid storage key: {key!r}")
        return os.path.join(self.base_dir, key)

    async def get_file(self, key: str) -> typing.BinaryIO:
        file_path = self._safe_path(key)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {key} not found")
        # In a real app this might return an async generator or stream, 
        # but for simplicity we'll just return a standard open file 
        return open(file_path, 'rb')

    async def delete_file(self, key: str) -> bool:
        file_path = self._safe_path(key)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
