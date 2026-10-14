import os
import uuid
import boto3

from botocore.exceptions import ClientError


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

GENERATED_FOLDER = os.path.join(
    BASE_DIR,
    "instance",
    "private_generated"
)

os.makedirs(
    GENERATED_FOLDER,
    exist_ok=True
)


R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")

R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")

R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")


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