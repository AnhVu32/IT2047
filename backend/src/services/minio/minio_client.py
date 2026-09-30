import os
import io
from datetime import timedelta
from urllib.parse import unquote, urlparse

import loguru
from minio import Minio
from minio import S3Error

import logging

logger = logging.getLogger("minio_logger")


class MinioClient:
    def __init__(self, config: dict):
        self._config = config
        self.minio_url = config.get("minio_end_point")
        self.access_key = config.get("minio_access_key_id")
        self.secret_key = config.get("minio_secret_access_key")
        self.minio_bucket_name = config.get("minio_bucket_name")
        self.secure = True if config.get("minio_secure") in ["True", "True", "TRUE", '1', 1] else False
        self._minio_client = None
        self.part_size = 10 * 1024 * 1024

    def start(self):
        self._minio_client = Minio(
            self.minio_url,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

    def minio_upload_file(self, content: io.BytesIO, s3_key: str, minio_bucket_name=None, part_size: int = None):
        try:
            content.seek(0)
            self._minio_client.put_object(
                self.minio_bucket_name if not minio_bucket_name else minio_bucket_name,
                object_name=s3_key,
                data=content,
                length=-1,
                part_size=self.part_size if not part_size else part_size,
            )
        except Exception as e:
            raise RuntimeError('Upload error for key "%s".' % s3_key) from e

    def minio_download_to_bytes(self, s3_key: str, output_path: str):
        try:
            self._minio_client.fget_object(
                bucket_name=self.minio_bucket_name,
                object_name=s3_key,
                file_path=output_path
            )
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise RuntimeError('The input key "%s" does not exist.' % s3_key) from e
            else:
                raise RuntimeError('Other download error for key "%s": %s' % (s3_key, e)) from e
        except Exception as e:
            raise RuntimeError('Other error for key "%s".' % s3_key) from e

    def minio_get_url(self, s3_key: str, hours: int = 24 * 7) -> str:
        return "https://" + self.minio_url + "/" + self.minio_bucket_name + "/" + s3_key

    def normalize_object_key(self, image_path: str) -> str:
        """Return a safe MinIO object key from a DB URL or object path."""
        raw_path = str(image_path or "").strip()
        if not raw_path:
            raise ValueError("Image path is required")

        parsed = urlparse(raw_path)
        path = unquote(parsed.path if parsed.scheme else raw_path).lstrip("/")
        bucket_prefix = f"{self.minio_bucket_name}/"
        if path.startswith(bucket_prefix):
            path = path[len(bucket_prefix):]

        parts = path.split("/")
        if not path.startswith("images/") or any(
            part in {"", ".", ".."} for part in parts
        ):
            raise ValueError("Invalid property image path")
        return path

    def minio_get_object(self, image_path: str):
        """Open an image stored in the configured private property bucket."""
        if self._minio_client is None:
            raise RuntimeError("MinIO client is not started")
        object_key = self.normalize_object_key(image_path)
        return self._minio_client.get_object(
            bucket_name=self.minio_bucket_name,
            object_name=object_key,
        )

    def stop(self):
        self._minio_client = None
