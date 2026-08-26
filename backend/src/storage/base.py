from abc import ABC, abstractmethod
import typing

class StorageBackend(ABC):
    @abstractmethod
    async def upload_file(self, key: str, file_stream: typing.BinaryIO) -> str:
        """
        Uploads a file stream to the storage backend.
        Returns the storage URI or path.
        """
        pass

    @abstractmethod
    async def upload_artifact(self, key: str, data: str) -> str:
        """
        Uploads an artifact atomically (e.g. JSON string).
        """
        pass

    @abstractmethod
    async def get_file(self, key: str) -> typing.BinaryIO:
        """
        Retrieves a file stream from the storage backend.
        """
        pass

    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        """
        Deletes a file from the storage backend.
        """
        pass
