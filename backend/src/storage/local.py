import io
import os
import aiofiles
import typing
from cryptography.fernet import Fernet, InvalidToken
from .base import StorageBackend

# Fernet tokens are URL-safe base64 of a 0x80 version byte, so they always start with this.
_FERNET_PREFIX = b"gAAAAA"

class LocalVolumeStorage(StorageBackend):
    """
    Stores files on a local volume. When an encryption key is provided, documents and
    artifacts are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256). Files written
    before encryption was enabled are still readable (they are detected and returned as-is).
    """

    def __init__(self, base_dir: str, encryption_key: str | None = None):
        self.base_dir = base_dir
        self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key) if encryption_key else None
        os.makedirs(self.base_dir, exist_ok=True)

    @property
    def encrypted(self) -> bool:
        return self._fernet is not None

    def _encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data) if self._fernet else data

    def _decrypt(self, data: bytes) -> bytes:
        if data.startswith(_FERNET_PREFIX):
            if not self._fernet:
                raise ValueError("File is encrypted but DOCUMENT_ENCRYPTION_KEY is not configured")
            try:
                return self._fernet.decrypt(data)
            except InvalidToken as e:
                raise ValueError("File could not be decrypted with the configured key") from e
        return data  # legacy plaintext file

    def _safe_path(self, key: str, base_dir: str | None = None) -> str:
        # Keys are generated UUIDs; refuse anything that could escape the storage directory.
        if not key or os.path.basename(key) != key or key in (".", ".."):
            raise ValueError(f"Invalid storage key: {key!r}")
        return os.path.join(base_dir or self.base_dir, key)

    @property
    def artifacts_dir(self) -> str:
        # Saved next to the documents directory, e.g. /app/data/artifacts (mounted as its own volume)
        return os.path.join(os.path.dirname(self.base_dir), 'artifacts')

    async def _atomic_write(self, file_path: str, data: bytes) -> None:
        temp_path = file_path + ".tmp"
        try:
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(data)
            os.replace(temp_path, file_path)  # atomic, replaces if exists
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    async def upload_file(self, key: str, file_stream: typing.BinaryIO) -> str:
        file_path = self._safe_path(key)
        await self._atomic_write(file_path, self._encrypt(file_stream.read()))
        return file_path

    async def upload_artifact(self, key: str, data: str) -> str:
        os.makedirs(self.artifacts_dir, exist_ok=True)
        file_path = self._safe_path(key, self.artifacts_dir)
        await self._atomic_write(file_path, self._encrypt(data.encode("utf-8")))
        return file_path

    async def get_artifact(self, key: str) -> str:
        file_path = self._safe_path(key, self.artifacts_dir)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Artifact {key} not found")
        async with aiofiles.open(file_path, 'rb') as f:
            return self._decrypt(await f.read()).decode("utf-8")

    async def get_file(self, key: str) -> typing.BinaryIO:
        file_path = self._safe_path(key)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {key} not found")
        async with aiofiles.open(file_path, 'rb') as f:
            return io.BytesIO(self._decrypt(await f.read()))

    async def delete_file(self, key: str) -> bool:
        file_path = self._safe_path(key)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    async def delete_artifact(self, key: str) -> bool:
        file_path = self._safe_path(key, self.artifacts_dir)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
