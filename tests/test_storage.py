import pytest

from app.platform.errors import DomainValidationError, NotFoundError
from app.platform.storage.service import StorageService


def test_put_get_roundtrip(tmp_path) -> None:
    """Stored text reads back identically via its storage URI."""
    storage = StorageService(tmp_path / "objects")
    uri = storage.put_text("runs/abc/00_identity/workspace_identity.md", "hello")
    assert uri == "local://runs/abc/00_identity/workspace_identity.md"
    assert storage.get_text(uri) == "hello"
    assert storage.get_text("runs/abc/00_identity/workspace_identity.md") == "hello"
    assert storage.exists(uri)


def test_get_missing_raises_not_found(tmp_path) -> None:
    storage = StorageService(tmp_path / "objects")
    with pytest.raises(NotFoundError):
        storage.get_text("does/not/exist.md")


def test_path_traversal_rejected(tmp_path) -> None:
    storage = StorageService(tmp_path / "objects")
    with pytest.raises(DomainValidationError):
        storage.put_text("../outside.md", "nope")
