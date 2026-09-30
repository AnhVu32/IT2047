import argparse
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


def parse_image_list(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []

    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]

    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass

        if text.startswith("http"):
            return [text]

    return []


def is_house_image_url(url: str) -> bool:
    lower_url = (url or "").lower()
    if not lower_url.startswith("http"):
        return False
    if "file4.batdongsan.com.vn" not in lower_url:
        return False
    if "/resize/200x200/" in lower_url:
        return False
    return True


def safe_name(value: str, fallback: str = "unknown") -> str:
    value = str(value or "").strip()
    if not value:
        value = fallback
    value = re.sub(r"[^0-9a-zA-Z._-]+", "_", value)
    value = value.strip("._")
    return value or fallback


def safe_folder_component(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"[\\/:*?\"<>|]+", "-", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or fallback


def file_name_from_url(url: str, index: int) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or f"image_{index}"
    base = safe_name(Path(name).stem, f"image_{index}")
    ext = Path(name).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"}:
        ext = ".jpg"
    return f"{index:03d}_{base}{ext}"


def collect_tasks(rows: List[Dict[str, Any]], max_items: Optional[int] = None) -> List[Tuple[int, str, str, str, str]]:
    tasks: List[Tuple[int, str, str, str, str]] = []
    seen = set()

    selected_rows = rows if max_items is None else rows[:max_items]

    for row_idx, row in enumerate(selected_rows, start=1):
        listing_id = safe_folder_component(row.get("Mã tin", ""), f"listing_{row_idx}")
        property_type = safe_folder_component(row.get("Loại BĐS", ""), "Khong ro loai")
        district = safe_folder_component(row.get("Quận huyện", ""), "Khong ro huyen")
        image_urls = parse_image_list(row.get("Danh sách ảnh"))
        for image_idx, url in enumerate(image_urls, start=1):
            if not is_house_image_url(url):
                continue
            key = (listing_id, url)
            if key in seen:
                continue
            seen.add(key)
            tasks.append((row_idx, property_type, district, listing_id, url))
    return tasks


def download_one(task: Tuple[int, str, str, str, str], output_root: Path, timeout: int) -> Tuple[bool, str]:
    row_idx, property_type, district, listing_id, url = task
    target_dir = output_root / property_type / district / listing_id
    target_dir.mkdir(parents=True, exist_ok=True)

    existing_files = list(target_dir.glob("*"))
    index = len(existing_files) + 1
    file_name = file_name_from_url(url, index)
    file_path = target_dir / file_name

    if file_path.exists() and file_path.stat().st_size > 0:
        return True, f"SKIP {file_path}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Referer": "https://batdongsan.com.vn/",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        content = response.content
        if not content:
            return False, f"EMPTY row={row_idx} url={url}"
        file_path.write_bytes(content)
        return True, f"OK {file_path}"
    except Exception as exc:
            return False, f"FAIL row={row_idx} id={listing_id} url={url} err={exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download listing images from JSON field 'Danh sách ảnh'.")
    parser.add_argument("--input", default="data/all_listings_full_detail.json", help="Input JSON file path")
    parser.add_argument("--output-dir", default="data/img", help="Output directory for images")
    parser.add_argument("--workers", type=int, default=12, help="Number of concurrent download workers")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--max-items", type=int, default=0, help="Limit number of listings for testing (0 = all)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    rows = json.loads(input_path.read_text(encoding="utf-8"))
    max_items = None if args.max_items <= 0 else args.max_items
    tasks = collect_tasks(rows, max_items=max_items)

    print(f"Input rows: {len(rows)}")
    print(f"Tasks (images): {len(tasks)}")
    print(f"Output dir: {output_root.resolve()}")

    success = 0
    failed = 0
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(download_one, task, output_root, args.timeout) for task in tasks]
        for i, future in enumerate(as_completed(futures), start=1):
            ok, message = future.result()
            with lock:
                if ok:
                    success += 1
                else:
                    failed += 1
            if i % 100 == 0 or not ok:
                print(f"[{i}/{len(tasks)}] {message}")

    print("Done")
    print(f"Downloaded: {success}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
