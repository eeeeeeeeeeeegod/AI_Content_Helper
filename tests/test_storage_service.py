from types import SimpleNamespace
from unittest.mock import MagicMock

import services.storage_service as storage_service


def test_save_generated_image_local(
    tmp_path,
    monkeypatch
):

    # 使用 pytest 臨時資料夾
    monkeypatch.setattr(
        storage_service,
        "GENERATED_FOLDER",
        str(tmp_path)
    )

    # 強制走 Local
    monkeypatch.setattr(
        storage_service,
        "R2_ENABLED",
        False
    )

    # 固定 UUID，方便測試檔名
    monkeypatch.setattr(
        storage_service.uuid,
        "uuid4",
        lambda: SimpleNamespace(
            hex="test-image"
        )
    )

    image_bytes = b"fake-image-data"

    filename = (
        storage_service
        .save_generated_image(
            image_bytes,
            user_id=1
        )
    )

    assert filename == (
        "test-image.png"
    )

    filepath = (
        tmp_path
        / "test-image.png"
    )

    assert filepath.exists()

    assert (
        filepath.read_bytes()
        == image_bytes
    )
    
def test_delete_stored_image_local(
    tmp_path,
    monkeypatch
):

    monkeypatch.setattr(
        storage_service,
        "GENERATED_FOLDER",
        str(tmp_path)
    )

    monkeypatch.setattr(
        storage_service,
        "R2_ENABLED",
        False
    )

    filepath = (
        tmp_path
        / "delete-me.png"
    )

    filepath.write_bytes(
        b"fake-image"
    )

    assert filepath.exists()

    storage_service.delete_stored_image(
        "delete-me.png"
    )

    assert not filepath.exists()
    
def test_save_generated_image_r2(
    monkeypatch
):

    fake_r2 = MagicMock()

    monkeypatch.setattr(
        storage_service,
        "R2_ENABLED",
        True
    )

    monkeypatch.setattr(
        storage_service,
        "R2_BUCKET_NAME",
        "test-bucket"
    )

    monkeypatch.setattr(
        storage_service,
        "r2_client",
        fake_r2
    )

    monkeypatch.setattr(
        storage_service.uuid,
        "uuid4",
        lambda: SimpleNamespace(
            hex="r2-image"
        )
    )

    image_bytes = b"fake-r2-image"

    result = (
        storage_service
        .save_generated_image(
            image_bytes,
            user_id=123
        )
    )

    assert result == (
        "users/123/r2-image.png"
    )

    fake_r2.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="users/123/r2-image.png",
        Body=image_bytes,
        ContentType="image/png"
    )

def test_delete_stored_image_r2(
    monkeypatch
):

    fake_r2 = MagicMock()

    monkeypatch.setattr(
        storage_service,
        "R2_ENABLED",
        True
    )

    monkeypatch.setattr(
        storage_service,
        "R2_BUCKET_NAME",
        "test-bucket"
    )

    monkeypatch.setattr(
        storage_service,
        "r2_client",
        fake_r2
    )

    storage_service.delete_stored_image(
        "users/123/test.png"
    )

    fake_r2.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="users/123/test.png"
    )