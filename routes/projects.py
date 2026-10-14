import io
import json

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    send_file,
    send_from_directory
)

from flask_login import (
    current_user,
    login_required
)

from botocore.exceptions import ClientError

from extensions import db

from models import (
    Brand,
    Project,
    ProjectVariant
)

from services.openai_client import client

from services.rag_service import (
    retrieve_brand_context
)

from services.ai_service import (
    generate_content,
    generate_platform_variants
)

from services.image_service import (
    IMAGE_SIZE_MAP,
    PLATFORM_DEFAULT_SIZE,
    build_image_prompt,
    generate_image
)

from services.storage_service import (
    delete_stored_image,
    R2_ENABLED,
    r2_client,
    R2_BUCKET_NAME,
    GENERATED_FOLDER
)


projects_bp = Blueprint(
    "projects",
    __name__
)


@projects_bp.route(
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
                            client,
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
                    client,
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
                        client,
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
                        ".private_project_image",
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

@projects_bp.route("/history")
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

@projects_bp.route("/project/<int:project_id>")
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

@projects_bp.route("/project/<int:project_id>/image")
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

@projects_bp.route(
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


# 3. 建立品牌基本資料
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

# 4. 檢索品牌知識庫
 
            search_query = f"""
主題：
{project.topic}

平台：
{project.platform}

其他需求：
{project.extra_requirement or ""}
"""

            rag_context = retrieve_brand_context(
                client,
                brand.id,
                search_query,
                top_k=4
            )

            print(
                "是否取得 RAG 內容：",
                bool(rag_context)
            )

# 5. 呼叫 AI 重新生成文案

        result = generate_content(
            client,
            project.topic,
            project.platform,
            project.tone,
            project.extra_requirement,
            brand_context,
            rag_context
        )

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
            ".project_detail",
            project_id=project.id
        )

    )


# 重新生成圖片

@projects_bp.route(
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
            client,
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
            ".project_detail",
            project_id=project.id
        )

    )


# 刪除作品

@projects_bp.route(
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

    # 先刪除作品的多平台版本
    
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
        url_for(".history")
    )


# 產生多平台版本

@projects_bp.route(
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
                client,
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
            ".project_detail",
            project_id=project.id
        )

    )
