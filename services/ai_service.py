import json

CONTENT_SCHEMA = {

    "type": "object",

    "properties": {

        "title": {
            "type": "string"
        },

        "caption": {
            "type": "string"
        },

        "cta": {
            "type": "string"
        },

        "hashtags": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "minItems": 5,
            "maxItems": 10
        },

        "image_prompt": {
            "type": "string"
        }

    },

    "required": [
        "title",
        "caption",
        "cta",
        "hashtags",
        "image_prompt"
    ],

    "additionalProperties": False
}

# ============================================
# 多平台 Structured Output Schema
# ============================================

PLATFORM_VARIANTS_SCHEMA = {

    "type": "object",

    "properties": {

        "variants": {

            "type": "array",

            "items": {

                "type": "object",

                "properties": {

                    "platform": {

                        "type": "string",

                        "enum": [
                            "Instagram",
                            "Facebook",
                            "Threads",
                            "X"
                        ]
                    },

                    "title": {
                        "type": "string"
                    },

                    "caption": {
                        "type": "string"
                    },

                    "cta": {
                        "type": "string"
                    },

                    "hashtags": {

                        "type": "array",

                        "items": {
                            "type": "string"
                        }

                    }

                },

                "required": [
                    "platform",
                    "title",
                    "caption",
                    "cta",
                    "hashtags"
                ],

                "additionalProperties": False
            },

            "minItems": 4,

            "maxItems": 4

        }

    },

    "required": [
        "variants"
    ],

    "additionalProperties": False
}

# ============================================
# 社群平台寫作規則
# ============================================

PLATFORM_RULES = {

    "Instagram": """
視覺導向的社群內容。
文案可以有適度情緒與節奏。
適合自然分段。
Hashtag 可以較完整，
但不要濫用。
""",

    "Facebook": """
資訊可以較完整。
適合清楚說明內容背景、特色與價值。
語氣自然且具有可讀性。
CTA 可以較明確。
""",

    "Threads": """
文字要具有自然聊天感。
避免過度正式或過度廣告化。
開頭可以直接、有話題性。
Hashtag 應少量使用。
""",

    "X": """
內容必須精簡。
快速傳達核心訊息。
避免冗長背景描述。
Hashtag 僅保留少量真正相關項目。
"""

}


def generate_content(
    client,
    topic,
    platform,
    tone,
    extra_requirement,
    brand_context="",
    rag_context=""
):

    prompt = f"""
請根據以下需求製作一篇社群媒體內容。

品牌基本資料：

{brand_context if brand_context else "未指定品牌"}


品牌知識庫檢索結果：

{rag_context if rag_context else "目前沒有額外品牌文件資訊"}

主題：
{topic}

發布平台：
{platform}

文案語氣：
{tone}

其他需求：
{extra_requirement if extra_requirement else "無"}

內容要求：

使用繁體中文撰寫。

請根據指定社群平台，
調整文案長度、節奏與表達方式。

標題簡潔且具有吸引力。

文案可以自然分段，
但不要輸出字面上的 \\n 或 \\n\\n 字串，
請直接使用正常換行。

文案具有自然的行銷效果，
但不要過度誇張。

CTA 必須簡潔並具有行動導向。

Hashtag 必須與主題高度相關。

image_prompt 必須使用英文。

image_prompt 必須描述：
- 主體
- 場景
- 氛圍
- 光線
- 構圖
- 攝影或插畫風格

image_prompt 不要要求圖片模型
直接產生大量文字。

不得自行捏造：
價格、
折扣比例、
活動日期、
統計數據、
產品功效、
品牌承諾。
"""


    response = client.responses.create(

        model="gpt-5.6-luna",

        instructions="""
你是一位專業社群媒體行銷企劃、
廣告文案撰寫者與視覺內容企劃助手。

你的工作是將使用者需求轉換成
適合實際社群平台發布的高品質內容。
""",

        input=prompt,

        text={

            "format": {

                "type": "json_schema",

                "name": "social_media_content",

                "strict": True,

                "schema": CONTENT_SCHEMA
            }

        },

        max_output_tokens=1000,

        store=False
    )


    content = response.output_text


    result = json.loads(content)

    # ============================================
    # 清理 AI 回傳的換行符號
    # ============================================
    
    for field in [
        "title",
        "caption",
        "cta",
        "image_prompt"
    ]:
    
        if (
            field in result
            and isinstance(
                result[field],
                str
            )
        ):
    
            result[field] = (
                result[field]
                .replace("\\n", "\n")
                .strip()
            )


    return result

# ============================================
# AI 多平台內容轉換
# ============================================

def generate_platform_variants(
    client,
    project
):

    platform_rules_text = ""

    for platform, rule in PLATFORM_RULES.items():

        platform_rules_text += f"""

【{platform}】

{rule}

"""


    prompt = f"""
請將以下社群內容重新改寫成
Instagram、Facebook、Threads、X
四個平台版本。


原始主題：

{project.topic}


原始標題：

{project.title}


原始文案：

{project.caption}


原始 CTA：

{project.cta}


平台規則：

{platform_rules_text}


重要要求：

1. 四個版本必須維持相同的核心事實。

2. 不得自行新增價格、折扣、日期、
數據、產品功效或不存在的活動資訊。

3. 不要只是把原文複製四次。

4. 必須真正根據不同平台重新調整：
文字長度、語氣、段落、CTA 與 Hashtag。

5. 使用繁體中文。

6. 不要輸出字面上的 \\n，
需要換行時請使用正常換行。

7. X 版本應特別精簡。

8. Threads 應較自然、有對話感。

9. Instagram 可以較有視覺與情緒感染力。

10. Facebook 可以提供較完整資訊。
"""


    response = client.responses.create(

        model="gpt-5.6-luna",

        instructions="""
你是一位專業的社群媒體內容策略師。

你的工作是將同一份品牌內容，
依照不同社群平台的使用習慣重新改寫。

必須維持原始內容的事實，
不能捏造使用者沒有提供的資訊。
""",

        input=prompt,

        text={

            "format": {

                "type": "json_schema",

                "name": "platform_variants",

                "strict": True,

                "schema": PLATFORM_VARIANTS_SCHEMA
            }

        },

        max_output_tokens=2500,

        store=False
    )


    content = response.output_text


    result = json.loads(content)


    # =================================
    # 清理換行
    # =================================

    for variant in result["variants"]:

        for field in [
            "title",
            "caption",
            "cta"
        ]:

            if isinstance(
                variant.get(field),
                str
            ):

                variant[field] = (
                    variant[field]
                    .replace("\\n", "\n")
                    .strip()
                )


    return result["variants"]
