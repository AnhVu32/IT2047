#!/usr/bin/env python3
"""Upload the images listed in Data/v3/images_manifest.csv to MinIO under their manifest key.

Runs inside the backend container (it has the minio SDK and the MinIO settings from .env):

  docker compose run --rm --no-deps \
    -v "$PWD/images:/images:ro" -v "$PWD/Data/v3:/v3:ro" backend python /v3/pipeline/upload_images_minio.py

Idempotent: objects that already exist with the same size are skipped, so an interrupted run can simply be repeated.
Content-Type comes from the detected file content (some files named .jpg are really PNG/WebP).
"""
import argparse
import csv
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from minio import Minio
from minio.error import S3Error

CONTENT_TYPES = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="/v3/images_manifest.csv")
    parser.add_argument("--images-root", default="/images", help="mount point of the repository images/ folder")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    client = Minio(os.environ["MINIO_END_POINT"], access_key=os.environ["MINIO_ACCESS_KEY_ID"],
                   secret_key=os.environ["MINIO_SECRET_ACCESS_KEY"],
                   secure=os.environ.get("MINIO_SECURE", "False").lower() == "true")
    bucket = os.environ["MINIO_BUCKET_NAME"]
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    with open(args.manifest, encoding="utf-8-sig", newline="") as f:
        items = list(csv.DictReader(f))
    print("bucket", bucket, "files", len(items), flush=True)

    lock, counts = threading.Lock(), {"uploaded": 0, "skipped": 0, "failed": 0}

    def upload(item):
        # local_path is relative to the repository root and starts with "images/".
        path = os.path.join(args.images_root, item["local_path"].split("/", 1)[1])
        size = os.path.getsize(path)
        try:
            if client.stat_object(bucket, item["key"]).size == size:
                return "skipped", item["key"]
        except S3Error as exc:
            if exc.code not in ("NoSuchKey", "NoSuchObject"):
                raise
        client.fput_object(bucket, item["key"], path, content_type=CONTENT_TYPES[item["detected_type"]])
        return "uploaded", item["key"]

    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(upload, it): it for it in items}
        for n, future in enumerate(as_completed(futures), 1):
            try:
                outcome, _ = future.result()
            except Exception as exc:  # noqa: BLE001 - keep going, report at the end
                outcome = "failed"
                failures.append((futures[future]["key"], repr(exc)))
            with lock:
                counts[outcome] += 1
            if n % 2000 == 0:
                print("progress", n, "/", len(items), counts, flush=True)
    print("done", counts, flush=True)
    for key, err in failures[:20]:
        print("FAILED", key, err, file=sys.stderr)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
