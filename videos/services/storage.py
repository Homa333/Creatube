import boto3

from django.conf import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION_NAME,
    )


def generate_upload_url(object_key, content_type):
    s3 = get_s3_client()

    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )


def get_object_metadata(object_key):
    """Return stored size and content type, or None if the object is missing."""
    s3 = get_s3_client()

    try:
        response = s3.head_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=object_key,
        )

    except s3.exceptions.ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")

        if error_code in ("404", "NoSuchKey", "NotFound"):
            return None

        raise

    return {
        "size": response["ContentLength"],
        "content_type": response.get("ContentType", ""),
    }


def object_exists(object_key):
    return get_object_metadata(object_key) is not None


def delete_object(object_key):
    """Delete an object, allowing storage errors to propagate."""
    s3 = get_s3_client()

    s3.delete_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=object_key,
    )
