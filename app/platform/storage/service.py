from functools import lru_cache
from pathlib import Path

from app.platform.errors import DomainValidationError, NotFoundError
from app.platform.settings.config import get_settings

URI_SCHEME = "local://"


class StorageService:
    """Object storage behind a filesystem backend.

    Keys are forward-slash paths (e.g. ``runs/<id>/00_identity/workspace_identity.md``);
    URIs are ``local://<key>``. The interface is deliberately S3-shaped so a bucket
    backend can replace this without touching callers.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        key = key.removeprefix(URI_SCHEME)
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise DomainValidationError(f"illegal storage key: {key}")
        return path

    def put_text(self, key: str, text: str) -> str:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return f"{URI_SCHEME}{key}"

    def get_text(self, key_or_uri: str) -> str:
        path = self._path_for(key_or_uri)
        if not path.is_file():
            raise NotFoundError(f"storage object not found: {key_or_uri}")
        return path.read_text(encoding="utf-8")

    def exists(self, key_or_uri: str) -> bool:
        return self._path_for(key_or_uri).is_file()


@lru_cache
def get_storage() -> StorageService:
    return StorageService(Path(get_settings().storage_root))
