import json
import numpy as np

from models import BrandChunk
from pypdf import PdfReader

MAX_PDF_PAGES = 20

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


def create_embeddings(
    client,
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


def retrieve_brand_context(
    client,
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


    query_embedding = create_embeddings(
            client,
            [query]
        )[0]


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
