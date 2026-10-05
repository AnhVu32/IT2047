#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass

# Hỗ trợ hiển thị UTF-8 an toàn trên Windows Console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from openpyxl import Workbook

DOMAIN = "https://batdongsan.com.vn"

VALID_CATEGORIES = [
    "ban-can-ho-chung-cu-tp-ho-chi-minh",
    "ban-nha-dat-tp-ho-chi-minh",
]
DEFAULT_CATEGORY = "ban-can-ho-chung-cu-tp-ho-chi-minh"


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


def build_page_url(category: str, page: int) -> str:
    if page <= 1:
        return f"{DOMAIN}/{category}?vrs=1&tpl=list"
    return f"{DOMAIN}/{category}/p{page}?vrs=1&tpl=list"


def create_scraper() -> curl_requests.Session:
    # Impersonate a real Chrome TLS/HTTP2 fingerprint so Cloudflare does not challenge us
    scraper = curl_requests.Session(impersonate="chrome")
    
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


PREFERRED_COLUMN_ORDER = [
    "title",
    "description_text",
    "listing_code",
    "listing_type",
    "posted_date",
    "expiry_date",
    "real_estate_type",
    "price_range",
    "price",
    "price_per_m2",
    "area_m2",
    "bedrooms",
    "address",
    "old_address",
    "province",
    "district",
    "link_location",
    "latitude",
    "longitude",
    "project_info",
    "property_features",
    "price_trend",
    "folder",
    "breadcrumb_folder",
    "url",
]


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
    category: str,
    pages: int,
    start_page: int = 1,
    timeout: int = 25,
    retries: int = 3,
    delay: float = 1.2,
    max_items: int = 0,
    with_detail: bool = True,
    jsonl_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
    track_log_path: Optional[Path] = None,
    seen_urls: Optional[set] = None,
    include_snippet: bool = True,
) -> List[Listing]:
    results: List[Listing] = []
    if seen_urls is None:
        seen_urls = set()

    log_track(
        track_log_path,
        f"[SESSION START] Phân khúc: {category} | Dự kiến cào trang: {start_page} -> {pages} | Giới hạn max_items: {max_items} | Đã có sẵn trong DB: {len(seen_urls)} tin",
    )

    current_page = start_page
    current_item_index = 0
    total_page_items = 0

    try:
        for page in range(start_page, pages + 1):
            current_page = page
            page_url = build_page_url(category, page)
            print(f"\nCrawling [{category}] page {page}/{pages}...")
            log_track(track_log_path, f"[START PAGE {page}/{pages}] URL: {page_url}")

            html = fetch_html(page_url, timeout=timeout, retries=retries, delay=delay)
            page_listings = parse_listings(html, source_page=page_url)
            total_page_items = len(page_listings)
            print(f"  -> Tim thay {total_page_items} the tin tren trang {page}.")
            log_track(track_log_path, f"  -> Trang {page}: Tìm thấy {total_page_items} tin danh sách.")

            page_saved_count = 0
            page_skipped_count = 0

            for idx, item in enumerate(page_listings, start=1):
                current_item_index = idx
                if item.url in seen_urls:
                    print(f"    [SKIP] Da co trong database: {item.title[:40]}...")
                    page_skipped_count += 1
                    continue
                seen_urls.add(item.url)

                if with_detail:
                    try:
                        item = enrich_listing_detail(
                            item, timeout=timeout, retries=retries, delay=delay
                        )
                        time.sleep(delay)
                    except Exception as e:
                        print(f"    [WARN] Khong the lay chi tiet tin {item.url}: {e}")
                        log_track(track_log_path, f"    [WARN] Lỗi chi tiết tin {item.url}: {e}")

                results.append(item)
                page_saved_count += 1

                # Ghi ngay lập tức từng tin vào file JSONL (Item-level Streaming)
                if jsonl_path:
                    row = to_dict_rows([item], include_snippet=include_snippet)[0]
                    append_jsonl(jsonl_path, row)
                    print(f"    [OK] [{len(seen_urls)}] Da luu: {item.title[:40]}...")

                if max_items > 0 and len(seen_urls) >= max_items:
                    print(f"\nDa dat gioi han max_items ({max_items}). Dung cao.")
                    if checkpoint_path:
                        save_checkpoint(
                            checkpoint_path,
                            {
                                "category": category,
                                "last_page": page,
                                "total_items": len(seen_urls),
                                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            },
                        )
                    log_track(
                        track_log_path,
                        f"[MAX_ITEMS REACHED] Đạt giới hạn {max_items} tin tại Trang {page} (tin thứ {idx}/{total_page_items}). Tổng DB: {len(seen_urls)} tin.",
                    )
                    return results

            if checkpoint_path:
                save_checkpoint(
                    checkpoint_path,
                    {
                        "category": category,
                        "last_page": page,
                        "total_items": len(seen_urls),
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    },
                )
            log_track(
                track_log_path,
                f"[PAGE COMPLETED] Hoàn tất Trang {page}/{pages} | Lưu mới: {page_saved_count} tin | Bỏ qua: {page_skipped_count} tin | Tổng DB hiện tại: {len(seen_urls)} tin",
            )

            time.sleep(delay)

        log_track(
            track_log_path,
            f"[SESSION SUCCESS] Hoàn thành trọn vẹn tất cả {pages} trang. Tổng DB hiện tại: {len(seen_urls)} tin.",
        )

    except KeyboardInterrupt:
        msg = f"[CRASH / INTERRUPTED] Người dùng bấm Ctrl+C dừng tiến trình tại Trang {current_page}/{pages} (đang xử lý tin thứ {current_item_index}/{total_page_items}). Tổng DB đã lưu an toàn: {len(seen_urls)} tin."
        print(f"\n{msg}")
        log_track(track_log_path, msg)
        raise

    except Exception as e:
        msg = f"[CRASH / ERROR] Tiến trình bị lỗi đột ngột tại Trang {current_page}/{pages} (đang xử lý tin thứ {current_item_index}/{total_page_items}) | Nguyên nhân: {e}. Tổng DB đã lưu an toàn: {len(seen_urls)} tin."
        print(f"\n{msg}")
        log_track(track_log_path, msg)
        raise

    return results


def to_dict_rows(items: Iterable[Listing], include_snippet: bool) -> List[dict]:
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

    ordered: List[str] = []
    used = set()

    for key in PREFERRED_COLUMN_ORDER:
        if key in seen and key not in used:
            ordered.append(key)
            used.add(key)

    feature_columns = sorted([key for key in fieldnames if key.startswith("dac_diem_")])
    project_columns = sorted([key for key in fieldnames if key.startswith("du_an_")])

    for key in feature_columns + project_columns:
        if key not in used:
            ordered.append(key)
            used.add(key)

    for key in fieldnames:
        if key not in used:
            ordered.append(key)

    return ordered


def append_jsonl(path: Path, row: dict) -> None:
    """Ghi 1 dòng JSON vào file jsonl (streaming append) và flush ngay xuống đĩa."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
        file.flush()


def load_seen_urls(jsonl_path: Path) -> set:
    """Nạp danh sách URL đã cào từ file jsonl để tránh cào trùng lặp."""
    seen = set()
    if not jsonl_path.exists():
        return seen
    try:
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    url = record.get("URL tin") or record.get("url")
                    if url:
                        seen.add(url)
                except Exception:
                    pass
    except Exception as e:
        print(f"[WARN] Khong the doc seen_urls tu {jsonl_path}: {e}")
    return seen


def load_checkpoint(checkpoint_path: Path) -> dict:
    """Đọc thông tin checkpoint tiến độ cào."""
    if checkpoint_path.exists():
        try:
            with checkpoint_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_checkpoint(checkpoint_path: Path, state: dict) -> None:
    """Lưu thông tin checkpoint tiến độ cào."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with checkpoint_path.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Khong the ghi checkpoint vao {checkpoint_path}: {e}")


def log_track(log_file: Optional[Path], message: str) -> None:
    """Ghi nhật ký tiến độ vào file track log và flush ngay lập tức."""
    if not log_file:
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except Exception:
        pass


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


def export_data(
    category: str,
    target_format: str,
    output_path: Optional[Path] = None,
    jsonl_path: Optional[Path] = None,
) -> Optional[Path]:
    """Chuyển đổi dữ liệu từ data.jsonl sang Excel (.xlsx), .json hoặc .csv"""
    if jsonl_path is None:
        jsonl_path = Path("data") / category / "data.jsonl"

    if not jsonl_path.exists():
        print(f"[EXPORT ERROR] Không tìm thấy file dữ liệu: {jsonl_path}")
        return None

    rows = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass

    if not rows:
        print(f"[EXPORT WARN] File {jsonl_path} không có bản ghi nào.")
        return None

    if output_path is None:
        output_dir = Path("data") / category
        output_path = output_dir / f"{category}.{target_format}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if target_format == "xlsx":
        save_xlsx(output_path, rows)
    elif target_format == "json":
        save_json(output_path, rows)
    elif target_format == "csv":
        save_csv(output_path, rows)
    else:
        print(f"[EXPORT ERROR] Định dạng không hợp lệ: {target_format}")
        return None

    print(f"[EXPORT OK] Đã xuất {len(rows)} bản ghi từ {jsonl_path.name} sang -> {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl dữ liệu nhà đất bán từ batdongsan.com.vn"
    )
    parser.add_argument(
        "--category",
        choices=VALID_CATEGORIES,
        default=DEFAULT_CATEGORY,
        help=f"Phân khúc BĐS cần cào ({', '.join(VALID_CATEGORIES)})",
    )
    parser.add_argument("--pages", type=int, default=1, help="Số trang cần crawl")
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Giới hạn số bản ghi (mặc định: 0 = không giới hạn, cào trọn vẹn theo số trang)",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "json", "csv", "xlsx"],
        default="jsonl",
        help="Định dạng output (mặc định: jsonl)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Đường dẫn file output (tùy chọn)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Tiếp tục cào từ checkpoint (không xóa file cũ, bỏ qua tin đã có)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=None,
        help="Trang bắt đầu cào (mặc định: tự động lấy từ checkpoint hoặc 1)",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Timeout request (giây)")
    parser.add_argument("--retries", type=int, default=3, help="Số lần retry")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
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
        "--export",
        choices=["xlsx", "json", "csv"],
        default=None,
        help="Xuất toàn bộ dữ liệu data.jsonl của category đã chọn sang file xlsx/json/csv mà không cần cào lại",
    )

    args = parser.parse_args()

    # Xử lý lệnh xuất dữ liệu độc lập
    if args.export:
        output_dir = Path("data") / args.category
        out_file = Path(args.output) if args.output else output_dir / f"{args.category}.{args.export}"
        export_data(category=args.category, target_format=args.export, output_path=out_file)
        return

    output_dir = Path("data") / args.category
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "checkpoint.json"

    if args.output:
        output_path = Path(args.output)
    else:
        if args.format == "jsonl":
            output_path = output_dir / "data.jsonl"
        else:
            output_path = output_dir / f"{args.category}.{args.format}"

    # Luôn xác định jsonl_path để stream dữ liệu chống crash
    if output_path.suffix == ".jsonl":
        jsonl_path = output_path
    else:
        jsonl_path = output_dir / "data.jsonl"

    start_page = 1
    seen_urls = set()

    # Tạo đường dẫn file track log theo thời gian bắt đầu
    current_time_str = time.strftime("%Y%m%d_%H%M%S")
    track_log_path = output_dir / f"track_{current_time_str}_{args.category}.log"
    print(f"[TRACK LOG] File nhat ky tien do: {track_log_path}")

    if args.resume:
        checkpoint = load_checkpoint(checkpoint_path)
        last_page = checkpoint.get("last_page", 1)
        start_page = args.start_page if args.start_page is not None else last_page
        seen_urls = load_seen_urls(jsonl_path)
        print(f"[RESUME] Tiếp tục cào cho phân khúc '{args.category}':")
        print(f"  - Dữ liệu đã có: {len(seen_urls)} tin")
        print(f"  - Bắt đầu từ trang: {start_page}")
    else:
        start_page = args.start_page if args.start_page is not None else 1
        # Xóa file cũ nếu có khi chạy lượt mới hoàn toàn
        if output_path.exists():
            output_path.unlink()
        if jsonl_path.exists() and jsonl_path != output_path:
            jsonl_path.unlink()
        if checkpoint_path.exists():
            checkpoint_path.unlink()

    items = crawl(
        category=args.category,
        pages=max(args.pages, start_page),
        start_page=start_page,
        timeout=max(args.timeout, 5),
        retries=max(args.retries, 1),
        delay=max(args.delay, 0.0),
        max_items=max(args.max_items, 0),
        with_detail=not args.skip_detail,
        jsonl_path=jsonl_path,
        checkpoint_path=checkpoint_path,
        track_log_path=track_log_path,
        seen_urls=seen_urls,
        include_snippet=args.include_snippet,
    )

    # Nếu format không phải jsonl, tự động xuất thêm file theo định dạng người dùng chọn
    if args.format != "jsonl":
        export_data(
            category=args.category,
            target_format=args.format,
            output_path=output_path,
            jsonl_path=jsonl_path,
        )

    print(f"\nDone. Tổng cộng {len(seen_urls)} listings trong database -> {output_path}")


if __name__ == "__main__":
    main()
