import os

from openai import OpenAI


api_key = os.getenv(
    "OPENAI_API_KEY"
)


if not api_key:

    raise RuntimeError(
        "找不到 OPENAI_API_KEY，請確認 .env"
    )


client = OpenAI(
    api_key=api_key
)