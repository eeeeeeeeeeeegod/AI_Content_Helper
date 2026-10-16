import base64

from types import SimpleNamespace
from unittest.mock import (
    MagicMock,
    patch
)

from services.image_service import (
    build_image_prompt,
    generate_image
)


def test_build_image_prompt():

    prompt = build_image_prompt(
        "一杯放在木桌上的精品咖啡",
        "commercial"
    )

    assert (
        "一杯放在木桌上的精品咖啡"
        in prompt
    )

    assert (
        "commercial"
        in prompt.lower()
        or "professional"
        in prompt.lower()
    )


def test_generate_image_success():

    # 假圖片內容
    fake_image_bytes = (
        b"fake-png-image-data"
    )

    fake_base64 = base64.b64encode(
        fake_image_bytes
    ).decode("utf-8")


    # 假 OpenAI client
    client = MagicMock()

    client.images.generate.return_value = (
        SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=fake_base64
                )
            ]
        )
    )


    # 不真的寫入 R2 / 硬碟
    with patch(
        "services.image_service.save_generated_image",
        return_value="users/1/test.png"
    ) as mock_save:

        filename = generate_image(
            client,
            "A professional coffee photo",
            "1024x1024",
            "low",
            user_id=1
        )


    assert filename == (
        "users/1/test.png"
    )

    client.images.generate.assert_called_once()

    mock_save.assert_called_once_with(
        fake_image_bytes,
        1
    )


def test_generate_image_passes_correct_settings():

    fake_base64 = base64.b64encode(
        b"image"
    ).decode("utf-8")

    client = MagicMock()

    client.images.generate.return_value = (
        SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=fake_base64
                )
            ]
        )
    )


    with patch(
        "services.image_service.save_generated_image",
        return_value="test.png"
    ):

        generate_image(
            client,
            "My image prompt",
            "1536x1024",
            "medium",
            user_id=10
        )


    call = (
        client.images.generate
        .call_args
    )

    kwargs = call.kwargs


    assert kwargs["prompt"] == (
        "My image prompt"
    )

    assert kwargs["size"] == (
        "1536x1024"
    )

    assert kwargs["quality"] == (
        "medium"
    )