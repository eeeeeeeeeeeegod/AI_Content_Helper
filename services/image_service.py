import base64

from services.storage_service import (
    save_generated_image
)

IMAGE_SIZE_MAP = {

    "square": "1024x1024",

    "portrait": "1024x1536",

    "landscape": "1536x1024"

}


PLATFORM_DEFAULT_SIZE = {

    "Instagram": "1024x1024",

    "Threads": "1024x1024",

    "Facebook": "1536x1024",

    "X": "1536x1024"

}


IMAGE_STYLE_MAP = {

    "commercial": """
professional commercial photography,
clean advertising composition,
high quality product marketing aesthetic
""",

    "lifestyle": """
natural lifestyle photography,
authentic candid feeling,
warm and approachable atmosphere
""",

    "minimal": """
minimalist visual design,
clean background,
simple composition,
modern elegant aesthetic
""",

    "cinematic": """
cinematic photography,
dramatic lighting,
strong visual depth,
premium cinematic atmosphere
""",

    "luxury": """
premium luxury advertising aesthetic,
elegant composition,
sophisticated lighting,
high-end brand campaign style
""",

    "illustration": """
modern digital illustration,
clean professional illustration,
vibrant visual storytelling
"""

}

def build_image_prompt(
    original_prompt,
    image_style
):

    style_instruction = IMAGE_STYLE_MAP.get(
        image_style,
        IMAGE_STYLE_MAP["commercial"]
    )


    final_prompt = f"""
Create a professional social media visual.

Main visual concept:
{original_prompt}

Visual style:
{style_instruction}

Important requirements:

- professional composition
- suitable for social media marketing
- visually clear focal point
- polished lighting
- high-quality visual appearance
- do not include logos unless explicitly requested
- do not invent brand names
- avoid unnecessary written text inside the image
"""


    return final_prompt


def generate_image(
    client,
    image_prompt,
    image_size,
    image_quality,
    user_id
):

    print("開始產生 AI 圖片...")

    print(
        "圖片尺寸：",
        image_size
    )

    print(
        "圖片品質：",
        image_quality
    )


    result = client.images.generate(

        model="gpt-image-2.5-flare",

        prompt=image_prompt,

        size=image_size,

        quality=image_quality,

        output_format="png"
    )


    image_base64 = (
        result.data[0].b64_json
    )


    image_bytes = base64.b64decode(
        image_base64
    )


    image_filename = save_generated_image(
        image_bytes,
        user_id
    )


    print(
        "圖片生成完成：",
        image_filename
    )


    return image_filename
