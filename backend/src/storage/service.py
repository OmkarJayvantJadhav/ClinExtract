import typing
import uuid
import filetype
from fastapi import UploadFile, HTTPException, status
from src.storage.base import StorageBackend

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg"
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class StorageService:
    def __init__(self, backend: StorageBackend):
        self.backend = backend

    def validate_file(self, file_bytes: bytes, filename: str) -> str:
        """
        Validates file size and magic bytes.
        Returns the detected mime type.
        """
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds maximum size of 10MB."
            )
        
        kind = filetype.guess(file_bytes)
        if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type. Allowed types: PDF, PNG, JPEG."
            )
        
        return kind.mime

    async def store_document(self, upload_file: UploadFile) -> typing.Tuple[str, str, int]:
        """
        Reads the file, validates it, and stores it using the backend.
        Returns (storage_key, mime_type, file_size).
        """
        file_bytes = await upload_file.read()
        mime_type = self.validate_file(file_bytes, upload_file.filename)
        
        # Reset the stream position for the backend
        await upload_file.seek(0)
        
        storage_key = str(uuid.uuid4())
        
        # We can pass upload_file.file directly which is a SpooledTemporaryFile (binary stream)
        await self.backend.upload_file(storage_key, upload_file.file)
        
        return storage_key, mime_type, len(file_bytes)

    async def store_artifact(self, storage_key: str, data: str) -> str:
        """
        Stores an artifact for a given storage key.
        Returns the path to the artifact.
        """
        return await self.backend.upload_artifact(f"{storage_key}_ocr.json", data)
