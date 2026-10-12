from flask import (
    Flask,
    render_template,
    request,
    url_for,
    redirect,
    send_file,
    send_from_directory,
    abort
)

from extensions import (
    db,
    migrate,
    login_manager,
    csrf
)

from models import (
    User,
    Project,
    Brand,
    BrandDocument,
    BrandChunk,
    ProjectVariant
)

from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader

import os
import json
import base64
import uuid
import numpy as np

import io
import boto3

from botocore.exceptions import ClientError

from datetime import datetime

from flask_login import (
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from flask_limiter import Limiter


# ============================================
# 1. 讀取環境變數
# ============================================

load_dotenv()

APP_ENV = os.getenv(
    "APP_ENV",
    "development"
).lower()

IS_PRODUCTION = (
    APP_ENV == "production"
)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "找不到 OPENAI_API_KEY，請確認 .env"
    )

# ============================================
# Cloudflare R2
# ============================================

R2_ACCOUNT_ID = os.getenv(
    "R2_ACCOUNT_ID"
)

R2_ACCESS_KEY_ID = os.getenv(
    "R2_ACCESS_KEY_ID"
)

R2_SECRET_ACCESS_KEY = os.getenv(
    "R2_SECRET_ACCESS_KEY"
)

R2_BUCKET_NAME = os.getenv(
    "R2_BUCKET_NAME"
)


R2_ENABLED = all([
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME
])


if R2_ENABLED:

    R2_ENDPOINT = (
        f"https://{R2_ACCOUNT_ID}"
        ".r2.cloudflarestorage.com"
    )

    r2_client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto"
    )

else:

    r2_client = None

# ============================================
# 2. OpenAI Client
# ============================================

client = OpenAI(
    api_key=api_key
)


# ============================================
# 3. Flask
# ============================================

app = Flask(__name__)

# ============================================
# Rate Limit
# ============================================

REDIS_URL = os.getenv(
    "REDIS_URL"
)


def get_client_ip():

    # Render 正式環境位於 Proxy 後方
    if IS_PRODUCTION:

        forwarded_for = request.headers.get(
            "X-Forwarded-For",
            ""
        )

        if forwarded_for:

            return (
                forwarded_for
                .split(",")[0]
                .strip()
            )

    # 本機開發環境
    return (
        request.remote_addr
        or "unknown"
    )


RATE_LIMIT_STORAGE = (
    REDIS_URL
    if REDIS_URL
    else "memory://"
)


limiter = Limiter(
    key_func=get_client_ip,
    app=app,
    default_limits=[],
    storage_uri=RATE_LIMIT_STORAGE,
    strategy="fixed-window"
)

# ============================================
# Flask Secret Key
# ============================================

app.config["SECRET_KEY"] = os.getenv(
    "FLASK_SECRET_KEY"
)

if not app.config["SECRET_KEY"]:

    raise RuntimeError(
        "找不到 FLASK_SECRET_KEY，請檢查 .env"
    )

csrf.init_app(app)

# ============================================
# 文件上傳限制
# ============================================

# 整個 HTTP 請求最大 6 MB
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

# 單一文件最大 5 MB
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024

# PDF 最多 20 頁
MAX_PDF_PAGES = 20

# 文件擷取後最多 20,000 字元
MAX_DOCUMENT_CHARS = 20_000

# 每次上傳最多產生 25 個 Chunk
MAX_DOCUMENT_CHUNKS = 25


# ============================================
# Database
# ============================================

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if DATABASE_URL:

    # 相容部分雲端平台提供的 postgres:// 格式
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )

    # 使用 psycopg 3
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )

    app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = DATABASE_URL

else:

    # 本機開發繼續使用 SQLite
    app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = "sqlite:///ai_content.db"


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

migrate.init_app(
    app,
    db,
    render_as_batch=True
)

login_manager.init_app(app)

login_manager.login_view = "login"

login_manager.login_message = (
    "請先登入後再使用此功能。"
)


# ============================================
# Session 設定
# ============================================

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    IS_PRODUCTION
)

# ============================================
# 4. 私人圖片儲存資料夾
# ============================================

GENERATED_FOLDER = os.path.join(
    app.instance_path,
    "private_generated"
)

os.makedirs(
    GENERATED_FOLDER,
    exist_ok=True
)

# ============================================
# 5. 圖片設定
# ============================================

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

# ============================================
# 載入使用者
# ============================================

@login_manager.user_loader
def load_user(user_id):

    try:

        return db.session.get(
            User,
            int(user_id)
        )

    except (ValueError, TypeError):

        return None

# ============================================
# 6. Structured Output Schema
# ============================================

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

# ============================================
# RAG：文字切割
# ============================================

def split_text(
    text,
    chunk_size=1200,
    overlap=200
):

    text = text.strip()

    if not text:

        return []


    chunks = []

    start = 0


    while start < len(text):

        end = start + chunk_size

        chunk = text[
            start:end
        ].strip()


        if chunk:

            chunks.append(
                chunk
            )


        start += (
            chunk_size - overlap
        )


    return chunks

# ============================================
# RAG：產生 Embedding
# ============================================

def create_embeddings(
    texts
):

    if not texts:

        return []


    response = client.embeddings.create(

        model="text-embedding-3-small",

        input=texts

    )


    embeddings = [

        item.embedding

        for item in response.data

    ]


    return embeddings

# ============================================
# RAG：Cosine Similarity
# ============================================

def cosine_similarity(
    vector_a,
    vector_b
):

    a = np.array(
        vector_a,
        dtype=np.float32
    )

    b = np.array(
        vector_b,
        dtype=np.float32
    )


    denominator = (
        np.linalg.norm(a)
        *
        np.linalg.norm(b)
    )


    if denominator == 0:

        return 0.0


    return float(

        np.dot(a, b)
        /
        denominator

    )

# ============================================
# RAG：品牌知識檢索
# ============================================

def retrieve_brand_context(
    brand_id,
    query,
    top_k=4
):

    chunks = (

        BrandChunk.query

        .filter_by(
            brand_id=brand_id
        )

        .all()

    )


    if not chunks:

        return ""


    # =============================
    # Query Embedding
    # =============================

    query_embedding = (
        create_embeddings(
            [query]
        )[0]
    )


    scored_chunks = []


    # =============================
    # 比較相似度
    # =============================

    for chunk in chunks:

        chunk_embedding = json.loads(
            chunk.embedding
        )


        score = cosine_similarity(

            query_embedding,

            chunk_embedding

        )


        scored_chunks.append(

            (
                score,
                chunk.content
            )

        )


    # =============================
    # 分數由高到低
    # =============================

    scored_chunks.sort(

        key=lambda item: item[0],

        reverse=True

    )


    # =============================
    # Top K
    # =============================

    top_chunks = scored_chunks[
        :top_k
    ]


    print(
        "RAG Top Results:"
    )


    for score, content in top_chunks:

        print(
            round(score, 4),
            content[:80]
        )


    context = "\n\n".join(

        content

        for score, content in top_chunks

    )


    return context

# ============================================
# RAG：讀取文件文字
# ============================================

def extract_text_from_file(
    uploaded_file
):

    filename = (
        uploaded_file.filename
        .lower()
    )


    # =================================
    # TXT
    # =================================

    if filename.endswith(".txt"):

        content = uploaded_file.read()

        try:

            return content.decode(
                "utf-8"
            )

        except UnicodeDecodeError:

            return content.decode(
                "big5",
                errors="ignore"
            )


    # =================================
    # PDF
    # =================================

    elif filename.endswith(".pdf"):

        reader = PdfReader(
            uploaded_file
        )

        # =================================
        # 檢查 PDF 頁數
        # =================================
    
        if len(reader.pages) > MAX_PDF_PAGES:
    
            raise ValueError(
                f"PDF 最多只能上傳 {MAX_PDF_PAGES} 頁"
            )

        text_parts = []


        for page in reader.pages:

            page_text = (
                page.extract_text()
                or ""
            )

            text_parts.append(
                page_text
            )


        return "\n".join(
            text_parts
        )


    else:

        raise ValueError(
            "目前只支援 PDF 與 TXT"
        )

# ============================================
# 7. AI 文案生成
# ============================================

def generate_content(
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


    result = json.loads(
        content
    )

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


    result = json.loads(
        content
    )


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

# ============================================
# 8. AI 圖片生成
# ============================================

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

# ============================================
# 圖片儲存
# ============================================

def save_generated_image(
    image_bytes,
    user_id
):

    filename = (
        f"{uuid.uuid4().hex}.png"
    )

    # ========================================
    # Cloudflare R2
    # ========================================

    if R2_ENABLED:

        object_key = (
            f"users/{user_id}/{filename}"
        )

        r2_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=object_key,
            Body=image_bytes,
            ContentType="image/png"
        )

        print(
            "R2 圖片上傳成功：",
            object_key
        )

        return object_key


    # ========================================
    # Local fallback
    # ========================================

    filepath = os.path.join(
        GENERATED_FOLDER,
        filename
    )

    with open(
        filepath,
        "wb"
    ) as f:

        f.write(
            image_bytes
        )

    print(
        "本機圖片儲存成功：",
        filename
    )

    return filename

# ============================================
# 刪除儲存圖片
# ============================================

def delete_stored_image(
    image_key
):

    if not image_key:
        return


    # ========================================
    # Cloudflare R2 圖片
    # ========================================

    if (
        R2_ENABLED
        and "/" in image_key
    ):

        try:

            r2_client.delete_object(
                Bucket=R2_BUCKET_NAME,
                Key=image_key
            )

            print(
                "R2 圖片刪除成功：",
                image_key
            )

        except ClientError as e:

            print(
                "R2 圖片刪除失敗：",
                e
            )

        return


    # ========================================
    # 舊版 Local 圖片
    # ========================================

    filepath = os.path.join(
        GENERATED_FOLDER,
        image_key
    )

    if os.path.isfile(
        filepath
    ):

        os.remove(
            filepath
        )

        print(
            "本機圖片刪除成功：",
            image_key
        )

def generate_image(
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

# ============================================
# HTTP Security Headers
# ============================================

@app.after_request
def add_security_headers(response):

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"

    response.headers[
        "X-Frame-Options"
    ] = "SAMEORIGIN"

    response.headers[
        "Referrer-Policy"
    ] = "strict-origin-when-cross-origin"

    if IS_PRODUCTION:

        response.headers[
            "Strict-Transport-Security"
        ] = "max-age=31536000; includeSubDomains"

    return response



# ============================================
# 上傳檔案過大
# ============================================

@app.errorhandler(413)
def request_entity_too_large(error):

    return (
        "上傳內容過大，請確認文件大小符合限制。",
        413
    )

# ============================================
# 404：找不到頁面
# ============================================

@app.errorhandler(404)
def page_not_found(error):

    return (
        "找不到此頁面。",
        404
    )


# ============================================
# 429：請求過於頻繁
# ============================================

@app.errorhandler(429)
def too_many_requests(error):

    return (
        "請求過於頻繁，請稍後再試。",
        429
    )


# ============================================
# 500：伺服器錯誤
# ============================================

@app.errorhandler(500)
def internal_server_error(error):

    try:
        db.session.rollback()

    except Exception:
        pass

    return (
        "伺服器發生錯誤，請稍後再試。",
        500
    )

# ============================================
# Health Check
# ============================================

@app.route("/health")
@limiter.exempt
def health():

    return {
        "status": "ok"
    }, 200

# ============================================
# 9. 首頁
# ============================================

@app.route(
    "/",
    methods=["GET", "POST"]
)
@login_required
def index():

    result = None

    error = None

    image_error = None

    brands = (
        Brand.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            Brand.name.asc()
        )
        .all()
    )

    if request.method == "POST":

        brand_id = request.form.get(
            "brand_id",
            ""
        )        

        topic = request.form.get(
            "topic",
            ""
        ).strip()


        platform = request.form.get(
            "platform",
            ""
        ).strip()


        tone = request.form.get(
            "tone",
            ""
        ).strip()


        extra_requirement = request.form.get(
            
            "extra_requirement",
            ""
        ).strip()
        
        # ============================================
        # 讀取圖片設定
        # ============================================
        
        image_ratio = request.form.get(
            "image_ratio",
            "auto"
        )


        image_style = request.form.get(
            "image_style",
            "commercial"
        )


        image_quality = request.form.get(
            "image_quality",
            "low"
        )



        if not topic:

            error = "請輸入主題"

        else:
            brand = None

            brand_context = ""
            
            rag_context = ""
            
            if brand_id:

                if not brand_id.isdecimal():
            
                    return (
                        "無效的品牌 ID",
                        400
                    )
            
                brand = (
                    Brand.query
                    .filter_by(
                        id=int(brand_id),
                        user_id=current_user.id
                    )
                    .first_or_404()
                )
            
            
                if brand:
            
                    brand_context = f"""
            品牌名稱：
            {brand.name}
            
            品牌介紹：
            {brand.description or "未提供"}
            
            目標客群：
            {brand.target_audience or "未提供"}
            
            品牌語氣：
            {brand.brand_tone or "未提供"}
            
            品牌特色：
            {brand.brand_features or "未提供"}
            
            產品與服務：
            {brand.products_services or "未提供"}
            
            禁止使用的詞：
            {brand.banned_words or "無"}
            
            其他品牌規則：
            {brand.notes or "無"}
            """
            
            
                    search_query = f"""
            主題：
            {topic}
            
            平台：
            {platform}
            
            其他需求：
            {extra_requirement}
            """
            
            
                    rag_context = (
                        retrieve_brand_context(
            
                            brand.id,
            
                            search_query,
            
                            top_k=4
            
                        )
                    )
            
            # =================================
            # AI 文案
            # =================================

            try:

                result = generate_content(

                    topic,
                    platform,
                    tone,
                    extra_requirement,
                    brand_context,
                    rag_context

                )

            except Exception as e:

                print(
                    "文字 AI Error:",
                    e
                )

                error = (
                    "AI 文案生成失敗，"
                    "請查看 CMD 錯誤訊息。"
                )

            # =================================
            # AI 圖片
            # =================================

            if result:

                try:

                    # =================================
                    # 圖片尺寸
                    # =================================
            
                    if image_ratio == "auto":
            
                        image_size = (
                            PLATFORM_DEFAULT_SIZE.get(
                                platform,
                                "1024x1024"
                            )
                        )
            
                    else:
            
                        image_size = (
                            IMAGE_SIZE_MAP.get(
                                image_ratio,
                                "1024x1024"
                            )
                        )
            
            
                    # =================================
                    # 圖片 Prompt
                    # =================================
            
                    final_image_prompt = (
                        build_image_prompt(
            
                            result["image_prompt"],
            
                            image_style
            
                        )
                    )
            
            
                    # =================================
                    # AI 圖片生成
                    # =================================
            
                    image_filename = generate_image(
            
                        final_image_prompt,
            
                        image_size,
            
                        image_quality,
                        
                        user_id=current_user.id
            
                    )
            
            
                    # 額外存一些資訊
                    result["image_size"] = image_size
            
                    result["image_style"] = image_style
            
                    result["image_quality"] = image_quality
                    
                    
                    
                    # =================================
                    # 儲存作品到 Database
                    # =================================
                    
                    project = Project(
                        
                        user_id=current_user.id,
                    
                        brand_id=brand.id if brand else None,
                    
                        topic=topic,
                    
                        platform=platform,
                    
                        tone=tone,
                    
                        extra_requirement=extra_requirement,
                    
                        title=result["title"],
                    
                        caption=result["caption"],
                    
                        cta=result["cta"],
                    
                        hashtags=json.dumps(
                            result["hashtags"],
                            ensure_ascii=False
                        ),
                    
                        image_prompt=result["image_prompt"],
                    
                        image_filename=image_filename,
                    
                        image_style=image_style,
                    
                        image_size=image_size,
                    
                        image_quality=image_quality
                    
                    )
                    
                    
                    db.session.add(project)
                    
                    db.session.commit()
                    
                    # 作品儲存成功後，取得私人圖片網址
                    result["image_url"] = url_for(
                        "private_project_image",
                        project_id=project.id
                    )
                    
                    print(
                        "作品已儲存到 Database，ID：",
                        project.id
                    )
            
                except Exception as e:
            
                    db.session.rollback()        
            
                    print(
                        "圖片 AI Error:",
                        e
                    )
            
                    image_error = (
                        "文案生成成功，"
                        "但圖片生成失敗。"
                    )


    return render_template(
    
        "index.html",
    
        result=result,
    
        error=error,
    
        image_error=image_error,
    
        brands=brands
    
    )

# ============================================
# 歷史作品
# ============================================

@app.route("/history")
@login_required
def history():

    projects = (
        Project.query.filter_by(
            user_id=current_user.id
        )
        .order_by(
            Project.created_at.desc()
        )
        .all()
    )

    return render_template(
        "history.html",
        projects=projects
    )

# ============================================
# 作品詳細頁
# ============================================

@app.route("/project/<int:project_id>")
@login_required
def project_detail(project_id):

    project = (
        Project.query
        .filter_by(
            id=project_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    # Database 裡的 hashtags 是 JSON 字串
    # 這裡轉回 Python List
    try:

        hashtags = json.loads(
            project.hashtags
        ) if project.hashtags else []

    except json.JSONDecodeError:

        hashtags = []

    variants = (
    
        ProjectVariant.query
    
        .filter_by(
            project_id=project.id
        )
    
        .order_by(
            ProjectVariant.id.asc()
        )
    
        .all()
    
    )

    variant_data = []
    
    
    for variant in variants:
    
        try:
    
            variant_hashtags = json.loads(
                variant.hashtags
            ) if variant.hashtags else []
    
        except json.JSONDecodeError:
    
            variant_hashtags = []
    
    
        variant_data.append({
    
            "id":
                variant.id,
    
            "platform":
                variant.platform,
    
            "title":
                variant.title,
    
            "caption":
                variant.caption,
    
            "cta":
                variant.cta,
    
            "hashtags":
                variant_hashtags
    
        })

    return render_template(
    
        "project_detail.html",
    
        project=project,
    
        hashtags=hashtags,
    
        variants=variant_data
    
    )

# ============================================
# 私人作品圖片
# ============================================

@app.route("/project/<int:project_id>/image")
@login_required
def private_project_image(project_id):

    # 確認作品屬於目前登入的使用者
    project = (
        Project.query
        .filter_by(
            id=project_id,
            user_id=current_user.id
        )
        .first_or_404()
    )

    # 沒有圖片
    if not project.image_filename:
        abort(404)

    image_key = project.image_filename


    # ========================================
    # Cloudflare R2 圖片
    # ========================================

    if (
        R2_ENABLED
        and "/" in image_key
    ):

        try:

            result = r2_client.get_object(
                Bucket=R2_BUCKET_NAME,
                Key=image_key
            )

            image_bytes = (
                result["Body"].read()
            )

            content_type = result.get(
                "ContentType",
                "image/png"
            )

        except ClientError as e:

            print(
                "R2 圖片讀取失敗：",
                e
            )

            error_code = (
                e.response
                .get("Error", {})
                .get("Code")
            )

            if error_code in (
                "NoSuchKey",
                "404"
            ):
                abort(404)

            raise


        response = send_file(
            io.BytesIO(image_bytes),
            mimetype=content_type
        )

        response.headers[
            "Cache-Control"
        ] = "private, no-store"

        return response


    # ========================================
    # 舊版 Local 圖片
    # ========================================

    response = send_from_directory(
        GENERATED_FOLDER,
        image_key
    )

    response.headers[
        "Cache-Control"
    ] = "private, no-store"

    return response

# ============================================
# 重新生成文案
# ============================================

@app.route(
    "/project/<int:project_id>/regenerate-content",
    methods=["POST"]
)
@login_required
def regenerate_content(project_id):

    project = (
        Project.query
        .filter_by(
            id=project_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    try:

        # ============================================
        # 1. 初始化品牌資料
        # ============================================

        brand_context = ""
        rag_context = ""

        print(
            "重新生成作品 ID：",
            project.id
        )

        print(
            "作品綁定的品牌 ID：",
            project.brand_id
        )

        # ============================================
        # 2. 讀取原本選擇的品牌
        # ============================================

        if project.brand_id is not None:

            brand = (
                Brand.query
                .filter_by(
                    id=project.brand_id,
                    user_id=current_user.id
                )
                .first()
            )

            if brand is None:

                return (
                    "找不到作品原本使用的品牌，"
                    "無法依照該品牌重新生成文案。",
                    409
                )

            # ========================================
            # 3. 建立品牌基本資料
            # ========================================

            brand_context = f"""
品牌名稱：
{brand.name}

品牌介紹：
{brand.description or "未提供"}

目標客群：
{brand.target_audience or "未提供"}

品牌語氣：
{brand.brand_tone or "未提供"}

品牌特色：
{brand.brand_features or "未提供"}

產品與服務：
{brand.products_services or "未提供"}

禁止使用的詞：
{brand.banned_words or "無"}

其他品牌規則：
{brand.notes or "無"}
"""

            # ========================================
            # 4. 檢索品牌知識庫
            # ========================================

            search_query = f"""
主題：
{project.topic}

平台：
{project.platform}

其他需求：
{project.extra_requirement or ""}
"""

            rag_context = retrieve_brand_context(
                brand.id,
                search_query,
                top_k=4
            )

            print(
                "是否取得 RAG 內容：",
                bool(rag_context)
            )

        # ============================================
        # 5. 呼叫 AI 重新生成文案
        # ============================================

        result = generate_content(

            project.topic,

            project.platform,

            project.tone,

            project.extra_requirement,

            brand_context,

            rag_context

        )

        # 更新 Database
        project.title = result["title"]


        # 更新 Database
        project.title = result["title"]

        project.caption = result["caption"]

        project.cta = result["cta"]


        project.hashtags = json.dumps(

            result["hashtags"],

            ensure_ascii=False

        )


        project.image_prompt = (
            result["image_prompt"]
        )


        db.session.commit()


        print(
            "重新生成文案成功，Project ID：",
            project.id
        )


    except Exception as e:

        print(
            "重新生成文案失敗：",
            e
        )

        return (
            "重新生成文案失敗，請查看 CMD。",
            500
        )


    return redirect(

        url_for(
            "project_detail",
            project_id=project.id
        )

    )

# ============================================
# 重新生成圖片
# ============================================

@app.route(
    "/project/<int:project_id>/regenerate-image",
    methods=["POST"]
)
@login_required
def regenerate_image(project_id):

    project = (
        Project.query
        .filter_by(
            id=project_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    try:

        # -------------------------
        # 建立最終圖片 Prompt
        # -------------------------

        final_image_prompt = (
            build_image_prompt(

                project.image_prompt,

                project.image_style
                or "commercial"

            )
        )


        # -------------------------
        # 記住舊圖片
        # -------------------------

        old_filename = (
            project.image_filename
        )


        # -------------------------
        # 生成新圖片
        # -------------------------

        new_filename = generate_image(

            final_image_prompt,

            project.image_size
            or "1024x1024",

            project.image_quality
            or "low",
            
            user_id=current_user.id

        )


        # -------------------------
        # Database 更新圖片
        # -------------------------

        project.image_filename = (
            new_filename
        )


        db.session.commit()


        # -------------------------
        # 刪除舊圖片
        # -------------------------

        delete_stored_image(
            old_filename
        )

        print(
            "重新生成圖片成功，Project ID：",
            project.id
        )


    except Exception as e:

        print(
            "重新生成圖片失敗：",
            e
        )

        return (
            "重新生成圖片失敗，請查看 CMD。",
            500
        )


    return redirect(

        url_for(
            "project_detail",
            project_id=project.id
        )

    )

# ============================================
# 刪除作品
# ============================================

@app.route(
    "/project/<int:project_id>/delete",
    methods=["POST"]
)
@login_required
def delete_project(project_id):

    project = (
        Project.query
        .filter_by(
            id=project_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    image_filename = (
        project.image_filename
    )

    # =================================
    # 先刪除作品的多平台版本
    # =================================
    
    ProjectVariant.query.filter_by(
        project_id=project.id
    ).delete(
        synchronize_session=False
    )

    # -------------------------
    # Database 刪除
    # -------------------------

    db.session.delete(
        project
    )

    db.session.commit()


    # -------------------------
    # 圖片檔案刪除
    # -------------------------

    delete_stored_image(
        image_filename
    )


    print(
        "作品已刪除：",
        project_id
    )


    return redirect(
        url_for("history")
    )

# ============================================
# 產生多平台版本
# ============================================

@app.route(
    "/project/<int:project_id>/generate-variants",
    methods=["POST"]
)
@login_required
def generate_variants(
    project_id
):

    project = (
        Project.query
        .filter_by(
            id=project_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    try:

        # =============================
        # 呼叫 AI
        # =============================

        variants = (
            generate_platform_variants(
                project
            )
        )


        # =============================
        # 刪除舊版本
        # =============================

        ProjectVariant.query.filter_by(
            project_id=project.id
        ).delete()


        # =============================
        # 儲存新版本
        # =============================

        for variant in variants:

            platform_variant = (
                ProjectVariant(

                    project_id=project.id,

                    platform=variant[
                        "platform"
                    ],

                    title=variant[
                        "title"
                    ],

                    caption=variant[
                        "caption"
                    ],

                    cta=variant[
                        "cta"
                    ],

                    hashtags=json.dumps(

                        variant[
                            "hashtags"
                        ],

                        ensure_ascii=False

                    )

                )
            )


            db.session.add(
                platform_variant
            )


        db.session.commit()


        print(
            "多平台版本生成成功，Project ID：",
            project.id
        )


    except Exception as e:

        db.session.rollback()


        print(
            "多平台版本生成失敗：",
            e
        )


        return (
            "多平台版本生成失敗，請查看 CMD。",
            500
        )


    return redirect(

        url_for(
            "project_detail",
            project_id=project.id
        )

    )

# ============================================
# 品牌管理
# ============================================

@app.route("/brands")
@login_required
def brands():

    brand_list = (
        Brand.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            Brand.created_at.desc()
        )
        .all()
    )

    return render_template(
        "brands.html",
        brands=brand_list
    )

# ============================================
# 新增品牌
# ============================================

@app.route(
    "/brands/new",
    methods=["GET", "POST"]
)
@login_required
def create_brand():

    error = None

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        target_audience = request.form.get(
            "target_audience",
            ""
        ).strip()

        brand_tone = request.form.get(
            "brand_tone",
            ""
        ).strip()

        brand_features = request.form.get(
            "brand_features",
            ""
        ).strip()

        products_services = request.form.get(
            "products_services",
            ""
        ).strip()

        banned_words = request.form.get(
            "banned_words",
            ""
        ).strip()

        notes = request.form.get(
            "notes",
            ""
        ).strip()


        if not name:

            error = "請輸入品牌名稱"

        else:

            brand = Brand(

                user_id=current_user.id,

                name=name,

                description=description,

                target_audience=target_audience,

                brand_tone=brand_tone,

                brand_features=brand_features,

                products_services=products_services,

                banned_words=banned_words,

                notes=notes

            )


            db.session.add(
                brand
            )

            db.session.commit()


            print(
                "品牌建立成功，ID：",
                brand.id
            )


            return redirect(
                url_for("brands")
            )


    return render_template(

        "brand_form.html",

        brand=None,

        error=error

    )

# ============================================
# 編輯品牌
# ============================================

@app.route(
    "/brands/<int:brand_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_brand(brand_id):

    brand = (
        Brand.query
        .filter_by(
            id=brand_id,
            user_id=current_user.id
        )
        .first_or_404()
    )
    error = None


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()


        if not name:

            error = "請輸入品牌名稱"

        else:

            brand.name = name

            brand.description = request.form.get(
                "description",
                ""
            ).strip()

            brand.target_audience = request.form.get(
                "target_audience",
                ""
            ).strip()

            brand.brand_tone = request.form.get(
                "brand_tone",
                ""
            ).strip()

            brand.brand_features = request.form.get(
                "brand_features",
                ""
            ).strip()

            brand.products_services = request.form.get(
                "products_services",
                ""
            ).strip()

            brand.banned_words = request.form.get(
                "banned_words",
                ""
            ).strip()

            brand.notes = request.form.get(
                "notes",
                ""
            ).strip()


            db.session.commit()


            print(
                "品牌更新成功：",
                brand.id
            )


            return redirect(
                url_for("brands")
            )


    return render_template(

        "brand_form.html",

        brand=brand,

        error=error

    )

# ============================================
# 刪除品牌
# ============================================

@app.route(
    "/brands/<int:brand_id>/delete",
    methods=["POST"]
)
@login_required
def delete_brand(brand_id):

    brand = (
        Brand.query
        .filter_by(
            id=brand_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    try:

        # =================================
        # 1. 先刪 BrandChunk
        # =================================

        deleted_chunks = (
            BrandChunk.query
            .filter_by(
                brand_id=brand.id
            )
            .delete(
                synchronize_session=False
            )
        )


        # =================================
        # 2. 再刪 BrandDocument
        # =================================

        deleted_documents = (
            BrandDocument.query
            .filter_by(
                brand_id=brand.id
            )
            .delete(
                synchronize_session=False
            )
        )

        Project.query.filter_by(
            brand_id=brand.id,
            user_id=current_user.id
        ).update(
            {"brand_id": None},
            synchronize_session=False
        )
        # =================================
        # 3. 最後刪 Brand
        # =================================

        db.session.delete(
            brand
        )


        # =================================
        # 4. 一次 Commit
        # =================================

        db.session.commit()


        print(
            "品牌刪除成功：",
            brand_id
        )

        print(
            "刪除文件數量：",
            deleted_documents
        )

        print(
            "刪除 Chunk 數量：",
            deleted_chunks
        )


    except Exception as e:

        db.session.rollback()


        print(
            "刪除品牌失敗：",
            e
        )


        return (
            "刪除品牌失敗，請查看 CMD。",
            500
        )


    return redirect(
        url_for("brands")
    )

# ============================================
# 品牌 RAG 知識庫
# ============================================

@app.route(
    "/brands/<int:brand_id>/knowledge"
)
@login_required
def brand_knowledge(
    brand_id
):

    brand = (
        Brand.query
        .filter_by(
            id=brand_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    documents = (

        BrandDocument.query

        .filter_by(
            brand_id=brand.id
        )

        .order_by(
            BrandDocument.created_at.desc()
        )

        .all()

    )


    return render_template(

        "brand_knowledge.html",

        brand=brand,

        documents=documents

    )

# ============================================
# 上傳品牌文件
# ============================================

@app.route(
    "/brands/<int:brand_id>/upload-document",
    methods=["POST"]
)
@login_required
def upload_brand_document(brand_id):

    brand = (
        Brand.query
        .filter_by(
            id=brand_id,
            user_id=current_user.id
        )
        .first_or_404()
    )


    uploaded_file = request.files.get(
        "document"
    )


    if (
        not uploaded_file
        or not uploaded_file.filename
    ):

        return (
            "請選擇文件",
            400
        )

    # ============================================
    # 檢查文件格式
    # ============================================
    
    filename = uploaded_file.filename.lower()
    
    if not filename.endswith((".txt", ".pdf")):
    
        return (
            "目前只支援 TXT 與 PDF 文件",
            400
        )
    
    
    # ============================================
    # 檢查單一文件大小
    # ============================================
    
    # 最多讀取 5 MB + 1 byte
    # 超過限制就停止，不讀取整份超大文件
    
    file_bytes = uploaded_file.read(
        MAX_DOCUMENT_BYTES + 1
    )
    
    if len(file_bytes) > MAX_DOCUMENT_BYTES:
    
        return (
            "文件大小不得超過 5 MB",
            413
        )
    
    
    # ============================================
    # 檢查是否為空檔案
    # ============================================
    
    if not file_bytes:
    
        return (
            "不能上傳空白文件",
            400
        )
    
    
    # ============================================
    # 基本 PDF 格式檢查
    # ============================================
    
    if filename.endswith(".pdf"):
    
        if not file_bytes[:1024].lstrip().startswith(
            b"%PDF-"
        ):
    
            return (
                "檔案內容不是有效的 PDF 格式",
                400
            )
    
    
    # ============================================
    # 將檔案讀取位置移回開頭
    # ============================================
    
    uploaded_file.stream.seek(0)

    try:
    
        # =================================
        # 1. 讀取文字
        # =================================
    
        text = extract_text_from_file(
            uploaded_file
        )
    
        if not text.strip():
    
            return (
                "文件中沒有可讀取的文字",
                400
            )
    
    
        # =================================
        # 2. 檢查文字長度
        # =================================
    
        if len(text) > MAX_DOCUMENT_CHARS:
    
            return (
                "文件文字過長，最多只能上傳 "
                f"{MAX_DOCUMENT_CHARS:,} 個字元",
                400
            )
    
    
        # =================================
        # 3. Chunking
        # =================================
    
        chunks = split_text(
            text
        )
    
        if not chunks:
    
            return (
                "無法建立文字區塊",
                400
            )
    
    
        # =================================
        # 4. 檢查 Chunk 數量
        # =================================
    
        if len(chunks) > MAX_DOCUMENT_CHUNKS:
    
            return (
                "文件產生的文字區塊過多，"
                f"最多允許 {MAX_DOCUMENT_CHUNKS} 個 Chunk",
                400
            )
    
    
        print(
            "文件 Chunk 數量：",
            len(chunks)
        )
    
    
        # =================================
        # 5. 通過檢查後，才呼叫 Embedding API
        # =================================
    
        embeddings = create_embeddings(
            chunks
        )




        # =============================
        # Document Database
        # =============================

        document = BrandDocument(

            brand_id=brand.id,

            filename=uploaded_file.filename

        )


        db.session.add(
            document
        )

        # 先取得 document.id
        db.session.flush()


        # =============================
        # Chunk Database
        # =============================

        for chunk, embedding in zip(
            chunks,
            embeddings
        ):

            brand_chunk = BrandChunk(

                brand_id=brand.id,

                document_id=document.id,

                content=chunk,

                embedding=json.dumps(
                    embedding
                )

            )


            db.session.add(
                brand_chunk
            )


        db.session.commit()


        print(
            "品牌文件建立 RAG 成功：",
            uploaded_file.filename
        )

    except ValueError as e:
    
        db.session.rollback()
    
        return (
            str(e),
            400
        )

    except Exception as e:

        db.session.rollback()

        print(
            "品牌文件上傳失敗：",
            e
        )

        return (
            "品牌文件處理失敗，請查看 CMD。",
            500
        )


    return redirect(

        url_for(
            "brand_knowledge",
            brand_id=brand.id
        )

    )

# ============================================
# 使用者註冊
# ============================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
@limiter.limit("3 per minute", methods=["POST"])
def register():

    if current_user.is_authenticated:

        return redirect(
            url_for("index")
        )


    error = None


    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )


        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # =================================
        # 檢查 Email
        # =================================

        if (
            len(email) > 255
            or email.count("@") != 1
            or not email.split("@")[0]
            or "." not in email.split("@")[1]
        ):

            error = "請輸入有效的 Email"


        # =================================
        # 檢查密碼
        # =================================

        elif len(password) < 12:

            error = "密碼長度至少需要 12 個字元"


        elif password != confirm_password:

            error = "兩次輸入的密碼不一致"


        else:

            # =============================
            # 確認 Email 沒有被註冊
            # =============================

            existing_user = (
                User.query
                .filter_by(
                    email=email
                )
                .first()
            )


            if existing_user:

                error = "這個 Email 已經被註冊"


            else:

              # 將使用者輸入的密碼轉成雜湊值

                hashed_password = generate_password_hash(
                    password
                )
                
                # 建立使用者資料
                
                user = User(
                    email=email,
                    password_hash=hashed_password
                )
                
                db.session.add(user)
                
                db.session.commit()


                print(
                    "新使用者建立成功，ID：",
                    user.id
                )


                # =============================
                # 註冊後自動登入
                # =============================

                login_user(
                    user
                )


                return redirect(
                    url_for("index")
                )


    return render_template(

        "register.html",

        error=error

    )

# ============================================
# 使用者登入
# ============================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("20 per hour", methods=["POST"])
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for("index")
        )


    error = None


    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )


        # =================================
        # 從 Database 找使用者
        # =================================

        user = (
            User.query
            .filter_by(
                email=email
            )
            .first()
        )

        # ============================================
        # 登入問題檢查
        # ============================================
        
        print("是否找到使用者：", user is not None)
        
        if user is not None:
        
            password_correct = check_password_hash(
                user.password_hash,
                password
            )
        
            print("密碼驗證結果：", password_correct)

        # =================================
        # 驗證帳號與密碼
        # =================================

        if (
            user is None
            or not check_password_hash(
                user.password_hash,
                password
            )
        ):

            error = "Email 或密碼錯誤"


        else:

            # =============================
            # 登入成功
            # =============================

            login_user(
                user
            )


            print(
                "使用者登入成功，ID：",
                user.id
            )


            return redirect(
                url_for("index")
            )


    return render_template(

        "login.html",

        error=error

    )

# ============================================
# 使用者登出
# ============================================

@app.route(
    "/logout",
    methods=["POST"]
)
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("login")
    )

# ============================================
# 10. 啟動 Flask
# ============================================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()

    app.run(
        debug=not IS_PRODUCTION
    )