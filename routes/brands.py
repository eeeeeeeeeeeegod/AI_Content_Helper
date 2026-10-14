import json

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from flask_login import (
    current_user,
    login_required
)

from extensions import db

from models import (
    Brand,
    BrandDocument,
    BrandChunk,
    Project
)

from services.rag_service import (
    split_text,
    create_embeddings,
    extract_text_from_file
)

from services.openai_client import client


brands_bp = Blueprint(
    "brands",
    __name__
)


MAX_DOCUMENT_BYTES = 5 * 1024 * 1024

MAX_DOCUMENT_CHARS = 20_000

MAX_DOCUMENT_CHUNKS = 25


@brands_bp.route("/brands")
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

@brands_bp.route(
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
                url_for(".brands")
            )


    return render_template(

        "brand_form.html",

        brand=None,

        error=error

    )

# ============================================
# 編輯品牌
# ============================================

@brands_bp.route(
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
                url_for(".brands")
            )


    return render_template(

        "brand_form.html",

        brand=brand,

        error=error

    )

# ============================================
# 刪除品牌
# ============================================

@brands_bp.route(
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
        url_for(".brands")
    )

# ============================================
# 品牌 RAG 知識庫
# ============================================

@brands_bp.route(
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

@brands_bp.route(
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
            client,
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
            ".brand_knowledge",
            brand_id=brand.id
        )

    )
