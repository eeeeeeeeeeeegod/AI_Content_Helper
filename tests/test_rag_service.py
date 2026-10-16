import json

from types import SimpleNamespace
from unittest.mock import MagicMock

from extensions import db

from models import (
    Brand,
    BrandDocument,
    BrandChunk
)

from services.rag_service import (
    split_text,
    cosine_similarity,
    retrieve_brand_context
)

def test_split_text_short_text():

    text = "這是一段很短的測試文字。"

    chunks = split_text(
        text
    )

    assert len(chunks) == 1

    assert chunks[0] == text
    
    
def test_split_text_long_text():

    text = "A" * 3000

    chunks = split_text(
        text,
        chunk_size=1200,
        overlap=200
    )

    assert len(chunks) > 1

    assert all(
        len(chunk) <= 1200
        for chunk in chunks
    )
    
def test_split_text_overlap():

    text = (
        "A" * 1000
        + "B" * 1000
        + "C" * 1000
    )

    chunks = split_text(
        text,
        chunk_size=1200,
        overlap=200
    )

    assert len(chunks) >= 3
    
def test_cosine_similarity_same_vector():

    vector_a = [
        1.0,
        0.0,
        0.0
    ]

    vector_b = [
        1.0,
        0.0,
        0.0
    ]

    similarity = cosine_similarity(
        vector_a,
        vector_b
    )

    assert similarity == 1.0
    
def test_cosine_similarity_orthogonal_vectors():

    vector_a = [
        1.0,
        0.0
    ]

    vector_b = [
        0.0,
        1.0
    ]

    similarity = cosine_similarity(
        vector_a,
        vector_b
    )

    assert similarity == 0.0
    
def test_retrieve_brand_context_returns_most_relevant_chunk(
    test_app
):

    # ============================================
    # 1. 建立測試品牌
    # ============================================

    brand = Brand(
        name="測試品牌"
    )

    db.session.add(
        brand
    )

    db.session.flush()


    # ============================================
    # 2. 建立測試文件
    # ============================================

    document = BrandDocument(
        brand_id=brand.id,
        filename="test.txt"
    )

    db.session.add(
        document
    )

    db.session.flush()


    # ============================================
    # 3. 建立三個不同的 Chunk
    # ============================================

    chunk_fitness = BrandChunk(
        brand_id=brand.id,
        document_id=document.id,
        content="我們提供專業健身課程與重量訓練。",
        embedding=json.dumps(
            [1.0, 0.0]
        )
    )

    chunk_coffee = BrandChunk(
        brand_id=brand.id,
        document_id=document.id,
        content="我們提供精品咖啡與手沖咖啡。",
        embedding=json.dumps(
            [0.0, 1.0]
        )
    )

    chunk_unrelated = BrandChunk(
        brand_id=brand.id,
        document_id=document.id,
        content="這是一段完全不相關的內容。",
        embedding=json.dumps(
            [-1.0, 0.0]
        )
    )

    db.session.add_all([
        chunk_fitness,
        chunk_coffee,
        chunk_unrelated
    ])

    db.session.commit()


    # ============================================
    # 4. 建立假的 OpenAI Client
    # ============================================

    client = MagicMock()

    client.embeddings.create.return_value = (
        SimpleNamespace(
            data=[
                SimpleNamespace(
                    embedding=[
                        1.0,
                        0.0
                    ]
                )
            ]
        )
    )


    # ============================================
    # 5. 執行 RAG Retrieval
    # ============================================

    context = retrieve_brand_context(
        client,
        brand.id,
        "我想知道健身課程",
        top_k=1
    )


    # ============================================
    # 6. 驗證最相關內容
    # ============================================

    assert (
        "專業健身課程"
        in context
    )

    assert (
        "精品咖啡"
        not in context
    )
    
def test_retrieve_brand_context_respects_top_k(
    test_app
):

    brand = Brand(
        name="Top K 測試品牌"
    )

    db.session.add(
        brand
    )

    db.session.flush()


    document = BrandDocument(
        brand_id=brand.id,
        filename="top_k_test.txt"
    )

    db.session.add(
        document
    )

    db.session.flush()


    chunks = [
        BrandChunk(
            brand_id=brand.id,
            document_id=document.id,
            content="第一相關內容",
            embedding=json.dumps(
                [1.0, 0.0]
            )
        ),

        BrandChunk(
            brand_id=brand.id,
            document_id=document.id,
            content="第二相關內容",
            embedding=json.dumps(
                [0.8, 0.2]
            )
        ),

        BrandChunk(
            brand_id=brand.id,
            document_id=document.id,
            content="第三相關內容",
            embedding=json.dumps(
                [0.0, 1.0]
            )
        )
    ]

    db.session.add_all(
        chunks
    )

    db.session.commit()


    client = MagicMock()

    client.embeddings.create.return_value = (
        SimpleNamespace(
            data=[
                SimpleNamespace(
                    embedding=[
                        1.0,
                        0.0
                    ]
                )
            ]
        )
    )


    context = retrieve_brand_context(
        client,
        brand.id,
        "測試查詢",
        top_k=2
    )


    assert (
        "第一相關內容"
        in context
    )

    assert (
        "第二相關內容"
        in context
    )

    assert (
        "第三相關內容"
        not in context
    )
    
def test_retrieve_brand_context_empty_brand(
    test_app
):

    brand = Brand(
        name="空白品牌"
    )

    db.session.add(
        brand
    )

    db.session.commit()


    client = MagicMock()


    context = retrieve_brand_context(
        client,
        brand.id,
        "任何問題",
        top_k=4
    )


    assert context == ""