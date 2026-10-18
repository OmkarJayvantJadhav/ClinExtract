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
    async def get_artifact(self, key: str) -> str:
        """
        Retrieves an artifact previously stored with upload_artifact.
        """
        pass

    @abstractmethod
    async def delete_artifact(self, key: str) -> bool:
        """
        Deletes an artifact.
        """
        pass

    @abstractmethod
    async def upload_binary_artifact(self, key: str, data: bytes) -> str:
        """
        Stores a derived binary file (e.g. a rendered page image) next to the artifacts.
        """
        pass

    @abstractmethod
    async def get_binary_artifact(self, key: str) -> bytes:
        """
        Retrieves a file stored with upload_binary_artifact; raises FileNotFoundError if absent.
        """
        pass

    @abstractmethod
    async def delete_artifacts_with_prefix(self, prefix: str) -> int:
        """
        Deletes every artifact whose key starts with `prefix`; returns how many were removed.
        """
        pass

    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        """
        Deletes a file from the storage backend.
        """
        pass
