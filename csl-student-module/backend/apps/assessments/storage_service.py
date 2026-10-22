import os
import uuid
import re
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class AssessmentPdfStorageService:
    """
    Storage service for assessment question paper PDFs.
    Integrates with Neon Object Storage or AWS S3 via S3-compatible API using boto3.
    Falls back gracefully to local storage when S3 credentials are not configured.
    """

    @classmethod
    def get_config(cls) -> Dict[str, Optional[str]]:
        """
        Reads object storage configuration exclusively from environment variables.
        Supports NEON_STORAGE_* prefixes with standard AWS_* fallbacks.
        Never logs access keys or secrets.
        """
        endpoint_url = (
            os.getenv("NEON_STORAGE_ENDPOINT_URL")
            or os.getenv("AWS_ENDPOINT_URL_S3")
            or os.getenv("AWS_S3_ENDPOINT_URL")
        )
        access_key = (
            os.getenv("NEON_STORAGE_ACCESS_KEY_ID")
            or os.getenv("AWS_ACCESS_KEY_ID")
        )
        secret_key = (
            os.getenv("NEON_STORAGE_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        region = (
            os.getenv("NEON_STORAGE_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )
        bucket = (
            os.getenv("NEON_STORAGE_BUCKET_NAME")
            or os.getenv("AWS_STORAGE_BUCKET_NAME")
        )

        return {
            "endpoint_url": endpoint_url.strip() if endpoint_url else None,
            "access_key": access_key.strip() if access_key else None,
            "secret_key": secret_key.strip() if secret_key else None,
            "region": region.strip() if region else "us-east-1",
            "bucket": bucket.strip() if bucket else None,
        }

    @classmethod
    def is_configured(cls) -> bool:
        """
        Returns True if S3 / Neon Object Storage credentials and bucket are configured.
        """
        cfg = cls.get_config()
        return bool(cfg["access_key"] and cfg["secret_key"] and cfg["bucket"])

    @classmethod
    def get_s3_client(cls):
        """
        Builds and returns a boto3 S3 client using configured credentials and endpoint.
        Uses signature_version s3v4 for broad Neon / AWS S3 compatibility.
        """
        import boto3
        from botocore.config import Config

        cfg = cls.get_config()
        client_kwargs: Dict[str, Any] = {
            "service_name": "s3",
            "aws_access_key_id": cfg["access_key"],
            "aws_secret_access_key": cfg["secret_key"],
            "region_name": cfg["region"],
            "config": Config(
                signature_version="s3v4",
                connect_timeout=10,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        if cfg["endpoint_url"]:
            client_kwargs["endpoint_url"] = cfg["endpoint_url"]

        return boto3.client(**client_kwargs)

    @classmethod
    def generate_object_key(cls, assessment_id: Any, original_filename: str) -> str:
        """
        Generates an unpredictable, collision-resistant, path-traversal-safe S3 object key.
        Never trusts raw client filenames in storage paths.
        """
        safe_base = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", original_filename.strip())
        safe_base = safe_base.lstrip(".") or "document"
        if not safe_base.lower().endswith(".pdf"):
            safe_base += ".pdf"

        # Unique token avoids filename collisions across assessments or multiple uploads
        unique_token = uuid.uuid4().hex[:12]
        return f"assessments/{assessment_id}/question_paper_{unique_token}_{safe_base}"

    @classmethod
    def save_pdf(cls, assessment_id: Any, raw_bytes: bytes, original_filename: str) -> Dict[str, Any]:
        """
        Uploads PDF to Neon Object Storage / S3 if configured.
        Returns a dict containing storage metadata:
        {
            "s3_key": str or None,
            "s3_bucket": str or None,
            "storage_type": "S3" | "LOCAL",
        }
        """
        if not cls.is_configured():
            logger.info("Object storage not configured; proceeding with local storage fallback.")
            return {
                "s3_key": None,
                "s3_bucket": None,
                "storage_type": "LOCAL",
            }

        cfg = cls.get_config()
        bucket = cfg["bucket"]
        object_key = cls.generate_object_key(assessment_id, original_filename)

        try:
            client = cls.get_s3_client()
            client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=raw_bytes,
                ContentType="application/pdf",
                Metadata={
                    "assessment_id": str(assessment_id),
                    "original_filename": original_filename[:100],
                },
            )
            logger.info(
                "Successfully uploaded assessment PDF to S3: bucket=%s, key=%s",
                bucket,
                object_key,
            )
            return {
                "s3_key": object_key,
                "s3_bucket": bucket,
                "storage_type": "S3",
            }
        except Exception as exc:
            logger.error("Failed to upload assessment PDF to S3: %s", exc)
            raise RuntimeError(f"Object storage upload failed: {str(exc)}") from exc

    @classmethod
    def get_pdf_bytes(cls, s3_key: str, s3_bucket: Optional[str] = None) -> bytes:
        """
        Streams PDF bytes from S3 / Neon Object Storage.
        """
        cfg = cls.get_config()
        bucket = s3_bucket or cfg["bucket"]
        if not bucket or not s3_key:
            return b""

        try:
            client = cls.get_s3_client()
            response = client.get_object(Bucket=bucket, Key=s3_key)
            body = response.get("Body")
            if body:
                return body.read()
            return b""
        except Exception as exc:
            logger.error("Error retrieving PDF from S3 key %s: %s", s3_key, exc)
            raise

    @classmethod
    def delete_pdf_object(cls, s3_key: str, s3_bucket: Optional[str] = None) -> bool:
        """
        Deletes PDF object from S3 / Neon Object Storage.
        Safe against missing keys, logging warnings without raising unhandled errors.
        """
        if not cls.is_configured() or not s3_key:
            return False

        cfg = cls.get_config()
        bucket = s3_bucket or cfg["bucket"]
        if not bucket:
            return False

        try:
            client = cls.get_s3_client()
            client.delete_object(Bucket=bucket, Key=s3_key)
            logger.info("Deleted PDF object from S3: bucket=%s, key=%s", bucket, s3_key)
            return True
        except Exception as exc:
            logger.warning("Failed to delete PDF object from S3 (%s): %s", s3_key, exc)
            return False
