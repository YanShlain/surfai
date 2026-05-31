import pytest

from app.config import Settings
from app.infrastructure.file_reader import SandboxFileReader


@pytest.fixture
def reader(tmp_path):
    settings = Settings(
        workflow_fs_root=str(tmp_path),
        call_service_timeout_seconds=10,
        call_service_max_timeout_seconds=60,
        call_service_max_retries=3,
        call_service_retry_base_seconds=0.5,
        call_service_retry_max_seconds=30,
        call_service_max_retries_cap=5,
    )
    return SandboxFileReader(settings=settings)


def test_read_text(reader, tmp_path):
    (tmp_path / "data.txt").write_text("hello", encoding="utf-8")
    assert reader.read_text("data.txt") == "hello"


def test_exists(reader, tmp_path):
    (tmp_path / "data.txt").write_text("hello", encoding="utf-8")
    assert reader.exists("data.txt")
    assert not reader.exists("missing.txt")


def test_sandbox_escape_blocked(reader, tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError):
        reader.read_text("../outside.txt")
