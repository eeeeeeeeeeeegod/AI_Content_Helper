import json

import pytest

from types import SimpleNamespace
from unittest.mock import MagicMock

from services.ai_service import (
    generate_content,
    generate_platform_variants
)

def create_mock_client(output_data):

    client = MagicMock()

    response = MagicMock()

    response.output_text = json.dumps(
        output_data,
        ensure_ascii=False
    )

    client.responses.create.return_value = response

    return client


def test_generate_content_success():

    fake_result = {
        "title": "夏日健身挑戰",
        "caption": "一起迎接充滿活力的夏天！",
        "cta": "立即開始你的健身計畫",
        "hashtags": [
            "#健身",
            "#夏日挑戰"
        ],
        "image_prompt": (
            "A modern fitness gym "
            "with bright natural lighting"
        )
    }

    client = create_mock_client(
        fake_result
    )

    result = generate_content(
        client,
        topic="夏季健身活動",
        platform="Instagram",
        tone="活潑",
        extra_requirement="強調年輕族群",
        brand_context="",
        rag_context=""
    )

    assert result["title"] == (
        "夏日健身挑戰"
    )

    assert result["caption"] == (
        "一起迎接充滿活力的夏天！"
    )

    assert result["cta"] == (
        "立即開始你的健身計畫"
    )

    assert len(
        result["hashtags"]
    ) == 2

    assert (
        "image_prompt"
        in result
    )


def test_generate_content_calls_openai():

    fake_result = {
        "title": "測試",
        "caption": "測試內容",
        "cta": "立即查看",
        "hashtags": [
            "#測試"
        ],
        "image_prompt": (
            "A professional "
            "social media image"
        )
    }

    client = create_mock_client(
        fake_result
    )

    generate_content(
        client,
        topic="測試主題",
        platform="Facebook",
        tone="專業",
        extra_requirement="",
        brand_context="",
        rag_context=""
    )

    client.responses.create.assert_called_once()


def test_generate_content_invalid_json():

    client = MagicMock()

    response = MagicMock()

    response.output_text = (
        "這不是合法 JSON"
    )

    client.responses.create.return_value = (
        response
    )

    with pytest.raises(
        json.JSONDecodeError
    ):

        generate_content(
            client,
            topic="測試",
            platform="Instagram",
            tone="專業",
            extra_requirement="",
            brand_context="",
            rag_context=""
        )
        
def test_generate_platform_variants_success():

    fake_result = {
        "variants": [
            {
                "platform": "Instagram",
                "title": "IG 標題",
                "caption": "Instagram 文案",
                "cta": "立即查看",
                "hashtags": [
                    "#Instagram",
                    "#測試"
                ]
            },
            {
                "platform": "Facebook",
                "title": "FB 標題",
                "caption": "Facebook 文案",
                "cta": "了解更多",
                "hashtags": [
                    "#Facebook",
                    "#測試"
                ]
            },
            {
                "platform": "Threads",
                "title": "Threads 標題",
                "caption": "Threads 文案",
                "cta": "一起討論",
                "hashtags": [
                    "#Threads",
                    "#測試"
                ]
            },
            {
                "platform": "X",
                "title": "X 標題",
                "caption": "X 文案",
                "cta": "立即查看",
                "hashtags": [
                    "#X",
                    "#測試"
                ]
            }
        ]
    }

    client = create_mock_client(
        fake_result
    )

    project = SimpleNamespace(
        topic="夏季健身活動",
        platform="Instagram",
        tone="活潑",
        extra_requirement="強調年輕族群",
        title="夏日健身挑戰",
        caption="一起迎接充滿活力的夏天！",
        cta="立即開始你的健身計畫",
        hashtags=json.dumps(
            [
                "#健身",
                "#夏日挑戰"
            ],
            ensure_ascii=False
        )
    )

    variants = generate_platform_variants(
        client,
        project
    )

    assert len(variants) == 4

    assert variants[0]["platform"] == (
        "Instagram"
    )

    assert variants[1]["platform"] == (
        "Facebook"
    )

    assert variants[2]["platform"] == (
        "Threads"
    )

    assert variants[3]["platform"] == (
        "X"
    )
    
def test_generate_platform_variants_calls_openai():

    fake_result = {
        "variants": [
            {
                "platform": "Instagram",
                "title": "IG",
                "caption": "IG 內容",
                "cta": "查看",
                "hashtags": []
            },
            {
                "platform": "Facebook",
                "title": "FB",
                "caption": "FB 內容",
                "cta": "查看",
                "hashtags": []
            },
            {
                "platform": "Threads",
                "title": "Threads",
                "caption": "Threads 內容",
                "cta": "查看",
                "hashtags": []
            },
            {
                "platform": "X",
                "title": "X",
                "caption": "X 內容",
                "cta": "查看",
                "hashtags": []
            }
        ]
    }

    client = create_mock_client(
        fake_result
    )

    project = SimpleNamespace(
        topic="測試",
        platform="Instagram",
        tone="專業",
        extra_requirement="",
        title="測試標題",
        caption="測試文案",
        cta="查看",
        hashtags="[]"
    )

    generate_platform_variants(
        client,
        project
    )

    client.responses.create.assert_called_once()