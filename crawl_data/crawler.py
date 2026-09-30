#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import cloudscraper
from bs4 import BeautifulSoup
from openpyxl import Workbook

BASE_URL = "https://batdongsan.com.vn/ban-nha-dat-tp-ho-chi-minh?vrs=1"
DOMAIN = "https://batdongsan.com.vn"


@dataclass
class Listing:
    title: str
    url: str
    price: str
    area_m2: str
    price_per_m2: str
    location: str
    posted_date: str
    contact_masked: str
    snippet: str
    source_page: str
    all_text: str
    all_tokens: str
    all_links: str
    image_urls: str
    card_html: str
    listing_code: str = ""
    listing_type: str = ""
    expiry_date: str = ""
    real_estate_type: str = ""
    province: str = ""
    district: str = ""
    description_text: str = ""
    price_range: str = ""
    bedrooms: str = ""
    folder: str = ""
    breadcrumb_folder: str = ""
    address: str = ""
    old_address: str = ""
    link_location: str = ""
    latitude: str = ""
    longitude: str = ""
    property_features: str = ""
    project_info: str = ""
    price_trend: str = ""


def build_page_url(page: int) -> str:
    if page <= 1:
        return BASE_URL
    return f"https://batdongsan.com.vn/ban-nha-dat-tp-ho-chi-minh/p{page}?vrs=1"


def create_scraper() -> cloudscraper.CloudScraper:
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "darwin", "mobile": False}
    )
    
    # Load cookies from .env if available
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        env_content = env_file.read_text(encoding="utf-8")
        for line in env_content.split("\n"):
            if line.startswith("COOKIES="):
                cookie_string = line.split("=", 1)[1].strip('"')
                # Parse cookie string and set cookies
                for cookie in cookie_string.split("; "):
                    if "=" in cookie:
                        name, value = cookie.split("=", 1)
                        scraper.cookies.set(name, value, domain=".batdongsan.com.vn")
                break
    
    return scraper


def fetch_html(url: str, timeout: int, retries: int, delay: float) -> str:
    scraper = create_scraper()
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            resp = scraper.get(url, timeout=timeout)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code} for {url}")

            html = resp.text
            blocked_markers = [
                "Just a moment...",
                "cf_chl",
                "Enable JavaScript and cookies to continue",
            ]
            if any(marker in html for marker in blocked_markers):
                raise RuntimeError("Blocked by anti-bot challenge")

            return html
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(delay * attempt)
            else:
                raise RuntimeError(f"Cannot fetch {url}: {error}") from error

    raise RuntimeError(f"Cannot fetch {url}: {last_error}")


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def is_house_image_url(url: str) -> bool:
    normalized = clean_text(url).lower()
    if not normalized:
        return False
    if "file4.batdongsan.com.vn" not in normalized:
        return False
    if "/resize/200x200/" in normalized:
        return False
    return "/crop/" in normalized or "/resize/" in normalized


def normalize_image_url_for_storage(url: str) -> str:
    normalized = clean_text(url)
    return normalized.replace("/resize/1275x717/", "/")


def extract_image_candidates_from_tag(tag) -> List[str]:
    candidates: List[str] = []
    direct_attrs = ["src", "data-src", "data-lazy", "data-lazy-src", "data-img"]
    for attr in direct_attrs:
        value = clean_text(tag.get(attr, ""))
        if value:
            candidates.append(value)

    for attr in ["srcset", "data-srcset"]:
        srcset_value = clean_text(tag.get(attr, ""))
        if not srcset_value:
            continue
        for part in srcset_value.split(","):
            image_part = clean_text(part.split(" ")[0])
            if image_part:
                candidates.append(image_part)

    return candidates


def image_resolution_score(url: str) -> int:
    match = re.search(r"/(?:resize|crop)/(\d+)x(\d+)/", url)
    if not match:
        return 0
    return int(match.group(1)) * int(match.group(2))


def image_file_key(url: str) -> str:
    return Path(urlparse(url).path).name.lower()


def prefer_image_url(candidate: str, current: str) -> bool:
    candidate_is_avatar = "/resize/200x200/" in candidate.lower()
    current_is_avatar = "/resize/200x200/" in current.lower()
    if candidate_is_avatar != current_is_avatar:
        return not candidate_is_avatar
    return image_resolution_score(candidate) > image_resolution_score(current)


def extract_detail_house_images(soup: BeautifulSoup) -> List[str]:
    image_tags = soup.select(
        ".re__pr-media-slide img, .re__pr-media-slide source, "
        ".re__media-preview img, .re__media-preview source, "
        ".re__media-thumbs img, .re__media-thumbs source"
    )

    ordered_keys: List[str] = []
    best_by_key: Dict[str, str] = {}

    for tag in image_tags:
        for candidate in extract_image_candidates_from_tag(tag):
            absolute_url = urljoin(DOMAIN, candidate)
            if not is_house_image_url(absolute_url):
                continue
            absolute_url = normalize_image_url_for_storage(absolute_url)
            key = image_file_key(absolute_url)
            if not key:
                continue

            if key not in best_by_key:
                best_by_key[key] = absolute_url
                ordered_keys.append(key)
                continue

            if prefer_image_url(absolute_url, best_by_key[key]):
                best_by_key[key] = absolute_url

    return [best_by_key[key] for key in ordered_keys if key in best_by_key]


def clean_multiline_text(text: str) -> str:
    if not text:
        return ""

    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned_lines: List[str] = []
    prev_blank = False

    for line in raw_lines:
        line = line.replace("\xa0", " ")
        line = re.sub(r"[ \t]+", " ", line).strip()

        if not line:
            if not prev_blank and cleaned_lines:
                cleaned_lines.append("")
            prev_blank = True
            continue

        if line == "." and cleaned_lines:
            cleaned_lines[-1] = f"{cleaned_lines[-1]}."
            prev_blank = False
            continue

        if cleaned_lines and cleaned_lines[-1].endswith(":") and re.match(
            r"^0\d[\d\s\*]+$", line
        ):
            cleaned_lines[-1] = f"{cleaned_lines[-1]} {line}"
            prev_blank = False
            continue

        cleaned_lines.append(line)
        prev_blank = False

    return "\n".join(cleaned_lines).strip()


def extract_description_text(soup: BeautifulSoup) -> str:
    description_node = soup.select_one(".re__section.re__pr-description .re__section-body")
    if not description_node:
        return ""

    for removable in description_node.select("script, style"):
        removable.decompose()

    for br in description_node.select("br"):
        br.replace_with("\n")

    raw_text = description_node.get_text("\n", strip=False)
    description_text = clean_multiline_text(raw_text)

    if description_text:
        return description_text

    return clean_text(description_node.get_text(" ", strip=True))


def extract_first(pattern: str, text: str, flags: int = re.IGNORECASE) -> str:
    match = re.search(pattern, text, flags)
    return clean_text(match.group(1)) if match else ""


def normalize_title(raw_title: str) -> str:
    title = clean_text(raw_title)
    title = re.sub(r"^\d+\s+", "", title)

    price_pos = re.search(
        r"\b\d+[\.,]?\d*\s*(?:tỷ|triệu|nghìn|đ|vnđ)\b", title, re.IGNORECASE
    )
    if price_pos:
        title = clean_text(title[: price_pos.start()])

    if " · " in title:
        title = clean_text(title.split(" · ")[0])

    return title


def extract_location(text_blob: str) -> str:
    parts = [clean_text(part) for part in text_blob.split("·") if clean_text(part)]
    if not parts:
        return ""

    location_hint = re.compile(
        r"(hà nội|hồ chí minh|đà nẵng|hải phòng|bình dương|đồng nai|khánh hòa|"
        r"hưng yên|long an|ninh bình|thái nguyên|cần thơ|quảng ninh|bắc ninh|"
        r"thanh hóa|nghệ an|lâm đồng|vũng tàu)",
        re.IGNORECASE,
    )

    for part in parts:
        if location_hint.search(part):
            return part

    if len(parts) >= 4:
        candidate = parts[3]
        if not re.search(r"\d", candidate):
            return candidate

    return ""


def find_listing_container(anchor):
    for parent in anchor.parents:
        if getattr(parent, "name", None) not in {"article", "li", "div"}:
            continue

        parent_text = clean_text(" ".join(parent.stripped_strings))
        if len(parent_text) < 40:
            continue

        listing_links = parent.select('a[href*="-pr"]')
        if len(listing_links) > 3:
            continue

        return parent

    return anchor


def parse_short_info_pairs(soup: BeautifulSoup) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for item in soup.select(".re__pr-short-info-item"):
        title_node = item.select_one(".title")
        value_node = item.select_one(".value")
        if not title_node or not value_node:
            continue
        title_text = clean_text(title_node.get_text(" ", strip=True))
        value_text = clean_text(value_node.get_text(" ", strip=True))
        if title_text and value_text:
            pairs[title_text] = value_text
    return pairs


def parse_specs_pairs(soup: BeautifulSoup) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for item in soup.select(".re__pr-specs-content-item"):
        title_node = item.select_one(".re__pr-specs-content-item-title")
        value_node = item.select_one(".re__pr-specs-content-item-value")
        if not title_node or not value_node:
            continue
        title_text = clean_text(title_node.get_text(" ", strip=True))
        value_text = clean_text(value_node.get_text(" ", strip=True))
        if title_text and value_text:
            pairs[title_text] = value_text
    return pairs


def parse_province_district(address_line_1: str) -> Tuple[str, str]:
    parts = [clean_text(part) for part in address_line_1.split(",") if clean_text(part)]
    if not parts:
        return "", ""
    province = parts[-1] if len(parts) >= 1 else ""
    district = parts[-2] if len(parts) >= 2 else ""
    return province, district


def extract_coordinates(detail_html: str, map_link: str) -> Tuple[str, str]:
    lat_match = re.search(r"latitude\s*:\s*([-+]?\d+\.\d+)", detail_html, re.IGNORECASE)
    lng_match = re.search(r"longitude\s*:\s*([-+]?\d+\.\d+)", detail_html, re.IGNORECASE)
    if lat_match and lng_match:
        return lat_match.group(1), lng_match.group(1)

    if map_link:
        query = parse_qs(urlparse(map_link).query)
        q_values = query.get("q", [])
        if q_values:
            lat_lng = q_values[0].split(",")
            if len(lat_lng) == 2:
                return clean_text(lat_lng[0]), clean_text(lat_lng[1])

    return "", ""


def parse_project_info(soup: BeautifulSoup) -> Dict[str, str]:
    project_card = soup.select_one(".re__ldp-project-info") or soup.select_one(
        ".re__project-card-info"
    )
    if not project_card:
        return {}

    project_text = clean_text(project_card.get_text(" ", strip=True))
    project_title_node = project_card.select_one(".re__project-title")
    project_name = (
        clean_text(project_title_node.get_text(" ", strip=True)) if project_title_node else ""
    )

    project_link_node = project_card.select_one("a[href]")
    project_link = ""
    if project_link_node:
        project_link = urljoin(DOMAIN, clean_text(project_link_node.get("href", "")))

    metrics = [clean_text(part) for part in project_text.split("·") if clean_text(part)]

    return {
        "project_name": project_name,
        "project_link": project_link,
        "project_raw_text": project_text,
        "project_metrics": " | ".join(metrics),
    }


def sanitize_column_key(raw_key: str) -> str:
    key = raw_key.lower()
    key = (
        key.replace("đ", "d")
        .replace("á", "a")
        .replace("à", "a")
        .replace("ạ", "a")
        .replace("ả", "a")
        .replace("ã", "a")
        .replace("ă", "a")
        .replace("ắ", "a")
        .replace("ằ", "a")
        .replace("ẳ", "a")
        .replace("ẵ", "a")
        .replace("ặ", "a")
        .replace("â", "a")
        .replace("ấ", "a")
        .replace("ầ", "a")
        .replace("ẩ", "a")
        .replace("ẫ", "a")
        .replace("ậ", "a")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ẻ", "e")
        .replace("ẽ", "e")
        .replace("ẹ", "e")
        .replace("ê", "e")
        .replace("ế", "e")
        .replace("ề", "e")
        .replace("ể", "e")
        .replace("ễ", "e")
        .replace("ệ", "e")
        .replace("í", "i")
        .replace("ì", "i")
        .replace("ỉ", "i")
        .replace("ĩ", "i")
        .replace("ị", "i")
        .replace("ó", "o")
        .replace("ò", "o")
        .replace("ỏ", "o")
        .replace("õ", "o")
        .replace("ọ", "o")
        .replace("ô", "o")
        .replace("ố", "o")
        .replace("ồ", "o")
        .replace("ổ", "o")
        .replace("ỗ", "o")
        .replace("ộ", "o")
        .replace("ơ", "o")
        .replace("ớ", "o")
        .replace("ờ", "o")
        .replace("ở", "o")
        .replace("ỡ", "o")
        .replace("ợ", "o")
        .replace("ú", "u")
        .replace("ù", "u")
        .replace("ủ", "u")
        .replace("ũ", "u")
        .replace("ụ", "u")
        .replace("ư", "u")
        .replace("ứ", "u")
        .replace("ừ", "u")
        .replace("ử", "u")
        .replace("ữ", "u")
        .replace("ự", "u")
        .replace("ý", "y")
        .replace("ỳ", "y")
        .replace("ỷ", "y")
        .replace("ỹ", "y")
        .replace("ỵ", "y")
    )
    key = re.sub(r"[^a-z0-9]+", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    return key


def to_title_from_key(raw_key: str) -> str:
    cleaned = raw_key.replace("_", " ").strip()
    return cleaned.title()


VI_COLUMN_MAP = {
    "title": "Tiêu đề",
    "url": "URL tin",
    "price": "Giá",
    "area_m2": "Diện tích",
    "price_per_m2": "Đơn giá/m²",
    "location": "Khu vực",
    "posted_date": "Ngày đăng",
    "contact_masked": "SĐT (ẩn)",
    "snippet": "Mô tả ngắn",
    "source_page": "Trang nguồn",
    "all_text": "Toàn bộ text hiển thị",
    "all_tokens": "Toàn bộ token",
    "all_links": "Tất cả liên kết",
    "image_urls": "Danh sách ảnh",
    "card_html": "HTML card",
    "listing_code": "Mã tin",
    "listing_type": "Loại tin",
    "expiry_date": "Ngày hết hạn",
    "real_estate_type": "Loại BĐS",
    "province": "Tỉnh thành",
    "district": "Quận huyện",
    "description_text": "Thông tin mô tả",
    "price_range": "Khoảng giá",
    "bedrooms": "Phòng ngủ",
    "folder": "Folder",
    "address": "Địa chỉ",
    "old_address": "Địa chỉ trước sát nhập",
    "link_location": "Link Location",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "property_features": "Đặc điểm bất động sản",
    "project_info": "Thông tin dự án",
}


VI_PREFERRED_COLUMN_ORDER = [
    "Tiêu đề",
    "Thông tin mô tả",
    "Mã tin",
    "Loại tin",
    "Ngày đăng",
    "Ngày hết hạn",
    "Loại BĐS",
    "Khoảng giá",
    "Diện tích",
    "Phòng ngủ",
    "Địa chỉ",
    "Địa chỉ trước sát nhập",
    "Tỉnh thành",
    "Quận huyện",
    "Link Location",
    "Latitude",
    "Longitude",
    "Thông tin dự án",
    "Đặc điểm bất động sản",
    "Folder",
    "URL tin",
]


def to_vi_column_name(column_key: str) -> str:
    if column_key in VI_COLUMN_MAP:
        return VI_COLUMN_MAP[column_key]

    if column_key.startswith("dac_diem_"):
        suffix = column_key.replace("dac_diem_", "", 1)
        return f"Đặc điểm - {to_title_from_key(suffix)}"

    if column_key.startswith("du_an_"):
        suffix = column_key.replace("du_an_", "", 1)
        return f"Dự án - {to_title_from_key(suffix)}"

    return column_key


def rename_row_keys_to_vi(rows: List[dict]) -> List[dict]:
    renamed_rows: List[dict] = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            new_row[to_vi_column_name(key)] = value
        renamed_rows.append(new_row)
    return renamed_rows


def enrich_listing_detail(
    listing: Listing, timeout: int, retries: int, delay: float
) -> Listing:
    detail_html = fetch_html(listing.url, timeout=timeout, retries=retries, delay=delay)
    soup = BeautifulSoup(detail_html, "lxml")

    short_info = parse_short_info_pairs(soup)
    specs_info = parse_specs_pairs(soup)
    project_info_map = parse_project_info(soup)

    title_node = soup.select_one("h1.re__pr-title") or soup.select_one("h1")
    detail_title = clean_text(title_node.get_text(" ", strip=True)) if title_node else ""

    detail_description = extract_description_text(soup)
    detail_images = extract_detail_house_images(soup)

    address_line_1_node = soup.select_one(".re__address-line-1")
    address_line_2_node = soup.select_one(".re__address-line-2")
    address_line_1 = (
        clean_text(address_line_1_node.get_text(" ", strip=True)) if address_line_1_node else ""
    )
    address_line_2 = (
        clean_text(address_line_2_node.get_text(" ", strip=True)) if address_line_2_node else ""
    )

    map_iframe = soup.select_one(".re__pr-map iframe")
    map_link = ""
    if map_iframe:
        map_link = clean_text(map_iframe.get("data-src") or map_iframe.get("src") or "")

    latitude, longitude = extract_coordinates(detail_html, map_link)

    breadcrumb_links = [
        clean_text(node.get_text(" ", strip=True))
        for node in soup.select(".re__breadcrumb a")
        if clean_text(node.get_text(" ", strip=True))
    ]
    # Tạo folder dạng breadcrumb (giữ cả "Bán")
    breadcrumb_folder = "/".join(breadcrumb_links) if breadcrumb_links else ""
    # Lấy phần tử cuối của breadcrumb (thường là loại BĐS: Căn hộ chung cư, Nhà riêng, v.v.)
    real_estate_type = breadcrumb_links[-1] if breadcrumb_links else ""
    
    # Nếu phần tử cuối là tên dự án/khu vực, lấy phần tử trước đó
    if len(breadcrumb_links) >= 4:
        # Breadcrumb format thường là: Bán > TP HCM > Quận X > Loại BĐS [> Tên dự án]
        # Lấy phần tử index -1 hoặc -2
        potential_type = breadcrumb_links[-1]
        # Nếu phần tử cuối chứa "tại" => đó là tên dự án, lấy phần trước
        if " tại " in potential_type.lower():
            # Extract loại BĐS từ chuỗi "Căn hộ chung cư tại Dự Án X"
            real_estate_type = potential_type.split(" tại ")[0].strip()

    province, district = parse_province_district(address_line_1)

    listing_code = short_info.get("Mã tin", "")
    if not listing_code:
        code_match = re.search(r"-pr(\d+)", listing.url)
        listing_code = code_match.group(1) if code_match else ""

    folder = ""
    path_parts = [part for part in urlparse(listing.url).path.split("/") if part]
    if path_parts:
        folder = path_parts[0]

    listing.title = detail_title or listing.title
    listing.listing_code = listing_code
    listing.listing_type = short_info.get("Loại tin", "")
    listing.posted_date = short_info.get("Ngày đăng", listing.posted_date)
    listing.expiry_date = short_info.get("Ngày hết hạn", "")
    listing.real_estate_type = real_estate_type
    listing.description_text = detail_description or listing.snippet
    if detail_images:
        listing.image_urls = json.dumps(detail_images, ensure_ascii=False)
    listing.price_range = short_info.get("Khoảng giá", listing.price)
    listing.area_m2 = short_info.get("Diện tích", listing.area_m2)
    listing.bedrooms = short_info.get("Phòng ngủ", specs_info.get("Số phòng ngủ", ""))
    listing.folder = folder
    listing.breadcrumb_folder = breadcrumb_folder
    listing.address = address_line_1
    listing.old_address = address_line_2
    listing.link_location = map_link
    listing.latitude = latitude
    listing.longitude = longitude
    listing.province = province
    listing.district = district
    listing.real_estate_type = listing.real_estate_type or listing.folder.replace("-", " ")

    # Extract price trend (% tăng/giảm giá trong 1 năm)
    price_trend = ""
    price_trend_elem = soup.select_one(".re__block-ldp-pricing-cta.re__up-trend, .re__block-ldp-pricing-cta.re__down-trend")
    if price_trend_elem:
        price_trend = clean_text(price_trend_elem.get_text(" ", strip=True))

    listing.property_features = json.dumps(specs_info, ensure_ascii=False)
    listing.project_info = json.dumps(project_info_map, ensure_ascii=False)
    listing.price_trend = price_trend
    return listing


def extract_listing_from_anchor(anchor, source_page: str) -> Optional[Listing]:
    href = anchor.get("href", "")
    if not href or "-pr" not in href:
        return None

    if not re.search(r"-pr\d+", href):
        return None

    full_url = urljoin(DOMAIN, href)
    title = normalize_title(anchor.get_text(" ", strip=True))

    container = find_listing_container(anchor)
    text_blob = clean_text(" ".join(container.stripped_strings))

    if not title:
        title = normalize_title(text_blob[:180])

    price = extract_first(r"((?:\d+[\.,]?\d*)\s*(?:tỷ|triệu|nghìn|đ|vnđ))", text_blob)
    area = extract_first(r"((?:\d+[\.,]?\d*)\s*m²)", text_blob)
    price_per_m2 = extract_first(
        r"((?:\d+[\.,]?\d*)\s*(?:tr\/m²|triệu\/m²|tỷ\/m²))", text_blob
    )
    posted_date = extract_first(r"((?:\d{2}\/\d{2}\/\d{4}))", text_blob)
    if not posted_date:
        posted_date = extract_first(r"((?:Đăng\s+(?:hôm nay|hôm qua)))", text_blob)
    contact_masked = extract_first(r"((?:0\d{2,3}\s?\d{3}\s?\*{3}))", text_blob)

    location = extract_location(text_blob)

    snippet = text_blob[:350]

    all_tokens_list = [clean_text(part) for part in text_blob.split("·") if clean_text(part)]
    all_tokens = " | ".join(all_tokens_list)

    links = []
    seen_links = set()
    for link_tag in container.select("a[href]"):
        link_href = clean_text(link_tag.get("href", ""))
        if not link_href:
            continue
        link_abs = urljoin(DOMAIN, link_href)
        if link_abs in seen_links:
            continue
        seen_links.add(link_abs)
        links.append(link_abs)
    all_links = json.dumps(links, ensure_ascii=False)

    images = []
    seen_images = set()
    for img_tag in container.select("img, source"):
        candidates: List[str] = []

        direct_attrs = [
            "src",
            "data-src",
            "data-lazy",
            "data-lazy-src",
            "data-img",
        ]
        for attr in direct_attrs:
            value = clean_text(img_tag.get(attr, ""))
            if value:
                candidates.append(value)

        srcset_attrs = ["srcset", "data-srcset"]
        for attr in srcset_attrs:
            srcset_value = clean_text(img_tag.get(attr, ""))
            if not srcset_value:
                continue
            for part in srcset_value.split(","):
                image_part = clean_text(part.split(" ")[0])
                if image_part:
                    candidates.append(image_part)

        for image_src in candidates:
            image_abs = urljoin(DOMAIN, image_src)
            if not is_house_image_url(image_abs):
                continue
            image_abs = normalize_image_url_for_storage(image_abs)
            if image_abs in seen_images:
                continue
            seen_images.add(image_abs)
            images.append(image_abs)
    image_urls = json.dumps(images, ensure_ascii=False)

    card_html = str(container)

    return Listing(
        title=title,
        url=full_url,
        price=price,
        area_m2=area,
        price_per_m2=price_per_m2,
        location=location,
        posted_date=posted_date,
        contact_masked=contact_masked,
        snippet=snippet,
        source_page=source_page,
        all_text=text_blob,
        all_tokens=all_tokens,
        all_links=all_links,
        image_urls=image_urls,
        card_html=card_html,
    )


def parse_listings(html: str, source_page: str) -> List[Listing]:
    soup = BeautifulSoup(html, "lxml")
    anchors = soup.select("a[href]")

    listings: List[Listing] = []
    seen = set()

    for anchor in anchors:
        listing = extract_listing_from_anchor(anchor, source_page)
        if listing is None:
            continue

        if listing.url in seen:
            continue

        seen.add(listing.url)
        listings.append(listing)

    return listings


def crawl(
    pages: int,
    timeout: int,
    retries: int,
    delay: float,
    max_items: int,
    with_detail: bool,
    output_path: Optional[Path] = None,
    include_snippet: bool = True,
    vi_columns: bool = True,
) -> List[Listing]:
    results: List[Listing] = []
    seen_urls = set()

    for page in range(1, pages + 1):
        page_url = build_page_url(page)
        print(f"Crawling page {page}/{pages}...")
        html = fetch_html(page_url, timeout=timeout, retries=retries, delay=delay)
        page_listings = parse_listings(html, source_page=page_url)

        page_results = []
        for item in page_listings:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)

            if with_detail:
                try:
                    item = enrich_listing_detail(
                        item, timeout=timeout, retries=retries, delay=delay
                    )
                    time.sleep(delay)
                except Exception:
                    pass

            results.append(item)
            page_results.append(item)

            if max_items > 0 and len(results) >= max_items:
                break

        # Ghi ngay sau mỗi trang
        if output_path and page_results:
            rows = to_dict_rows(page_results, include_snippet=include_snippet, vi_columns=vi_columns)
            append_to_json(output_path, rows)
            print(f"  → Saved {len(rows)} items from page {page} (total: {len(results)})")

        if max_items > 0 and len(results) >= max_items:
            return results

        time.sleep(delay)

    return results


def to_dict_rows(items: Iterable[Listing], include_snippet: bool, vi_columns: bool) -> List[dict]:
    rows = []
    for item in items:
        row = asdict(item)

        property_features_map = {}
        project_info_map = {}
        try:
            property_features_map = json.loads(row.get("property_features", "") or "{}")
        except Exception:
            property_features_map = {}
        try:
            project_info_map = json.loads(row.get("project_info", "") or "{}")
        except Exception:
            project_info_map = {}

        for feature_key, feature_value in property_features_map.items():
            row[f"dac_diem_{sanitize_column_key(feature_key)}"] = feature_value

        for project_key, project_value in project_info_map.items():
            row[f"du_an_{sanitize_column_key(project_key)}"] = project_value

        if not include_snippet:
            row.pop("snippet", None)
        rows.append(row)

    if vi_columns:
        rows = rename_row_keys_to_vi(rows)

    return rows


def collect_fieldnames(rows: List[dict]) -> List[str]:
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            fieldnames.append(key)

    if "Tiêu đề" in fieldnames:
        ordered: List[str] = []
        used = set()

        for key in VI_PREFERRED_COLUMN_ORDER:
            if key in seen and key not in used:
                ordered.append(key)
                used.add(key)

        feature_columns = sorted(
            [key for key in fieldnames if key.startswith("Đặc điểm - ")]
        )
        project_columns = sorted([key for key in fieldnames if key.startswith("Dự án - ")])

        for key in feature_columns + project_columns:
            if key not in used:
                ordered.append(key)
                used.add(key)

        for key in fieldnames:
            if key not in used:
                ordered.append(key)

        return ordered

    return fieldnames


def save_json(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)


def append_to_json(path: Path, new_rows: List[dict]) -> None:
    """Append new rows to JSON file (load existing, merge, save)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    existing_rows = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as file:
                existing_rows = json.load(file)
        except Exception:
            existing_rows = []
    
    existing_rows.extend(new_rows)
    
    with path.open("w", encoding="utf-8") as file:
        json.dump(existing_rows, file, ensure_ascii=False, indent=2)


def save_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as file:
            file.write("")
        return

    fieldnames = collect_fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_xlsx(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "listings"

    if not rows:
        workbook.save(path)
        return

    fieldnames = collect_fieldnames(rows)
    sheet.append(fieldnames)

    for row in rows:
        sheet.append([row.get(field, "") for field in fieldnames])

    workbook.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl dữ liệu nhà đất bán từ batdongsan.com.vn"
    )
    parser.add_argument("--pages", type=int, default=1, help="Số trang cần crawl")
    parser.add_argument(
        "--max-items",
        type=int,
        default=100,
        help="Giới hạn số bản ghi (0 = không giới hạn)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "xlsx"],
        default="json",
        help="Định dạng output",
    )
    parser.add_argument(
        "--output",
        default="data/batdongsan_nha_dat_ban.json",
        help="Đường dẫn file output",
    )
    parser.add_argument("--timeout", type=int, default=25, help="Timeout request (giây)")
    parser.add_argument("--retries", type=int, default=3, help="Số lần retry")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        help="Khoảng nghỉ giữa request/trang (giây)",
    )
    parser.add_argument(
        "--include-snippet",
        action="store_true",
        help="Giữ trường snippet trong output",
    )
    parser.add_argument(
        "--skip-detail",
        action="store_true",
        help="Bỏ qua crawl trang chi tiết, chỉ lấy dữ liệu từ trang danh sách",
    )
    parser.add_argument(
        "--vi-columns",
        dest="vi_columns",
        action="store_true",
        default=True,
        help="Đổi tên cột output sang tiếng Việt (mặc định: bật)",
    )
    parser.add_argument(
        "--raw-columns",
        dest="vi_columns",
        action="store_false",
        help="Giữ tên cột gốc (không đổi sang tiếng Việt)",
    )

    args = parser.parse_args()

    output_path = Path(args.output)
    
    # Xóa file cũ nếu có (để bắt đầu mới)
    if output_path.exists():
        output_path.unlink()

    items = crawl(
        pages=max(args.pages, 1),
        timeout=max(args.timeout, 5),
        retries=max(args.retries, 1),
        delay=max(args.delay, 0.0),
        max_items=max(args.max_items, 0),
        with_detail=not args.skip_detail,
        output_path=output_path if args.format == "json" else None,
        include_snippet=args.include_snippet,
        vi_columns=args.vi_columns,
    )

    # Nếu không phải JSON thì mới cần save (JSON đã save incremental)
    if args.format != "json":
        rows = to_dict_rows(
            items,
            include_snippet=args.include_snippet,
            vi_columns=args.vi_columns,
        )
        if args.format == "csv":
            save_csv(output_path, rows)
        else:
            save_xlsx(output_path, rows)

    print(f"Done. Crawled {len(items)} listings -> {output_path}")


if __name__ == "__main__":
    main()
