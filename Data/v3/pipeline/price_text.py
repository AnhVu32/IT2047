"""Read the asking price (tỷ VND) that a listing states in its own title/description.

Used only to audit `price_range` of the 2026 crawl (Data/v3/pipeline/fix_v3_quality.py).
Deterministic, standard library only.  `python price_text.py` runs the self-test.

Every money amount in a text ("17,5 tỷ", "6tỷ95", "6 tỷ 90 triệu", "980 triệu", "600tr") gets a
context class from the keyword nearest before it in the same clause, or from what follows it:

    positive    "giá 5 tỷ", "chỉ còn 5 tỷ", "về 5 tỷ", "bán 5 tỷ", "để lại 5 tỷ", "tổng giá: 5 tỷ"
    neutral     no keyword ("Nhà 4 tầng 5 tỷ")
    per_time    "30 triệu/tháng", "2 tỷ/năm", "30 triệu tháng"     rent or income
    per_area    "130 triệu/m²", "5 triệu/phòng"                     unit price
    rent        "HĐT 70 triệu", "thu nhập 30 triệu", "dòng tiền 1 tỷ", "TN: 600tr"
    discount    "giảm 1 tỷ", "bớt 300 triệu", "hạ giá 500 triệu", "lỗ 2 tỷ", "tốt hơn thị trường 5 tỷ"
    downpay     "trả trước 500 triệu", "vay 2 tỷ", "chỉ cần 1 tỷ", "vốn 3 tỷ", "708 triệu (30%)"
    settle      "thanh toán 7 tỷ" (usually the full price, sometimes a part of it)
    old         "giá cũ 8 tỷ", "định giá 13 tỷ", "giá giao dịch / kỳ vọng 137 tỷ", "từ 23 tỷ";
                X in "X về|còn|xuống Y"; X in "giá X ... giảm Y" (same sentence; Y is the new price
                when Y ≥ X/2, else Y is the discount)
    promo       "tặng 100 triệu", "chiết khấu", "hoa hồng", "voucher", "ưu đãi"
    range       "3 - 5 tỷ", "từ 20 - 2000 tỷ"

stated_price(): in the title, else the description: the positive amount (all positive amounts
equal; else the target of an "X về Y" chain; else the single "còn/về/xuống/giá mới" amount); with no
positive amount, the only distinct neutral amount. An approximate title amount ("nhỉnh 7 tỷ") gives
way to a close description price ("nay còn 7,89 tỷ"). None, with how="ambiguous" when a field states
several prices, or how="none" when it states none.
crawler_value(): the value the 2026 crawler stored for a text — the first "tỷ/triệu" amount of
the title (else of the description), whatever its context, with the "tỷ 750" tail dropped and
the "tr" abbreviation ignored. It is used to *explain* a stored price before correcting it.
"""
import re
import unicodedata

L = "a-zà-ỹđ"   # Vietnamese lowercase letters (patterns are compiled with IGNORECASE)

AMOUNT = re.compile(
    r"(?<![\d.,/])(?P<int>\d{1,4})(?:[.,](?P<dec>\d{1,3}))?\s*(?P<unit>tỷ|tỉ|ty|ti|triệu|trieu|tr)(?![" + L + r"])"
    r"(?:\s*(?P<tail>\d{1,3})(?P<tailunit>\s*(?:triệu|trieu|tr)(?![" + L + r"]))?"
    r"(?!\d|[.,]\d|\s*(?:m\b|m2|m²|%|tầng|lầu|pn|wc|phòng|năm|tháng|x\s*\d)))?",
    re.IGNORECASE)

AFTER_PER_TIME = re.compile(r"^\s*(?:đồng|đ|vnđ|vnd)?\s*(?:(?:/|mỗi|một|1|trên)\s*(?:tháng|thang|năm|nam|th\b|tuần|ngày)|tháng\b)",
                            re.IGNORECASE)
AFTER_PER_AREA = re.compile(r"^\s*(?:đồng|đ|vnđ|vnd)?\s*(?:/|trên|mỗi)\s*(?:1\s*)?(?:m\b|m2|m²|mét|phòng)",
                            re.IGNORECASE)
AFTER_PERCENT = re.compile(r"^\s*\(\s*\d{1,2}\s*%", re.IGNORECASE)
BEFORE_RANGE = re.compile(r"\d(?:[.,]\d+)?\s*(?:tỷ|tỉ|ty)?\s*[-–~]\s*$", re.IGNORECASE)
# "X ... về|còn|xuống Y": X is the old price (or a discount) and Y the current price.
VALUATION = re.compile(r"(?<![a-zà-ỹđ])(?:giá trị|định giá|quy đổi|giá thị trường|giá giao dịch|giá kỳ vọng|giá thực tế)"
                       r"(?![a-zà-ỹđ])", re.IGNORECASE)
APPROX_BEFORE = re.compile(r"(?<![a-zà-ỹđ])(?:nhỉnh|hơn|gần|trên|khoảng|tầm|xấp xỉ|ngót|~)\s*$", re.IGNORECASE)
AFTER_SUPERSEDED = re.compile(
    r"^[^.;!?|()\n]{0,20}?(?<![" + L + r"])(?:còn|về|xuống|nay|→|->|=>)(?![" + L + r"])[^.;!?|()\n\d]{0,12}\d",
    re.IGNORECASE)

KEYWORDS = [  # (class, pattern) — the keyword nearest to the amount decides its class
    ("rent", r"giá thuê|giá cho thuê|thuê|thue|hđt|hdt|hđ|hợp đồng|thu nhập|thu nhap|tn|thu về|dòng tiền|dong tien|doanh thu|lợi nhuận|"
             r"sinh lời|lãi|cashflow"),
    ("discount", r"giảm chào|hạ chào|hạ giá|giảm giá|giảm sâu|giảm sốc|giảm mạnh|giảm thẳng|giảm ngay|giảm|giam|bớt|hạ|lỗ|chênh|"
                 r"rẻ hơn|thấp hơn|tốt hơn|hơn thị trường|chiết khấu"),
    ("downpay", r"trả trước|tra truoc|vay|ngân hàng|bank|hỗ trợ|ho tro|chỉ cần|góp|cọc|vốn|nợ|trả góp"),
    ("settle", r"thanh toán|đóng"),
    ("old", r"giá trị|giá giao dịch|giá kỳ vọng|giá thực tế|vùng giá|giá cũ|giá củ|giá gốc|giá trước|định giá|giá thị trường|giá trung bình|giá khu vực|giá đất|từ khoảng|từ"),
    ("promo", r"tặng|voucher|lì xì|ưu đãi|hoa hồng|thưởng"),
    ("positive", r"giá cắt lỗ|giá bán cắt lỗ|giá xả|giá thanh lý|tổng giá|giá bán|giá giảm|giá hạ|giá sau giảm|giá mới|giá chốt|giá|chỉ|bán|còn|về|xuống|tl|"
                 r"thương lượng|chào|nay|mới|để lại|chốt"),
]
KW = re.compile("|".join(f"(?P<{c}>(?<![{L}])(?:{p})(?![{L}]))" for c, p in KEYWORDS), re.IGNORECASE)
CLAUSE_BREAK = re.compile(r"[,;.!?|()\n]|\s[-–]\s")
MAX_GAP = 25          # characters allowed between the keyword and the amount

NON_PRICE = {"per_time", "per_area", "rent", "discount", "downpay", "settle", "old", "promo", "range"}


def norm(text):
    text = unicodedata.normalize("NFC", str(text or ""))
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _value(m, keep_tail=True):
    whole, dec, unit = int(m.group("int")), m.group("dec"), m.group("unit").lower()
    tail, tailunit = m.group("tail"), m.group("tailunit")
    if unit in ("tỷ", "tỉ", "ty", "ti"):
        if dec:
            return float(f"{whole}.{dec}")
        if tail and keep_tail:
            return whole + (int(tail) / 1000.0 if tailunit else int(tail) / 10 ** len(tail))
        return float(whole)
    if dec or whole >= 1000:          # "1.500 triệu" etc. is not used for prices in this corpus
        return None
    return whole / 1000.0


def _context(before, after):
    """(class, keyword) for one amount."""
    if AFTER_PER_TIME.search(after):
        return "per_time", ""
    if AFTER_PER_AREA.search(after):
        return "per_area", ""
    if AFTER_PERCENT.search(after):
        return "downpay", "%"
    if BEFORE_RANGE.search(before):
        return "range", ""
    clause = CLAUSE_BREAK.split(before)[-1] if before else ""
    if VALUATION.search(clause):                 # "Giá trị căn thô quy đổi chỉ còn khoảng 16 tỷ"
        return "old", "valuation"
    last = None
    for k in KW.finditer(clause):
        last = k
    if last is None or len(clause) - last.end() > MAX_GAP:
        return "neutral", ""
    return last.lastgroup, last.group(0).lower()


def amounts(text):
    """All money amounts in `text` with their context class, in order of appearance."""
    text = norm(text)
    out = []
    for m in AMOUNT.finditer(text):
        val = _value(m)
        if val is None or val <= 0:
            continue
        before, after = text[max(0, m.start() - 60):m.start()], text[m.end():m.end() + 30]
        cls, kw = _context(before, after)
        approx = bool(APPROX_BEFORE.search(before))
        out.append(dict(value=round(val, 4), raw=m.group(0), start=m.start(), end=m.end(), cls=cls, kw=kw, approx=approx,
                        superseded=bool(AFTER_SUPERSEDED.search(after)), chain_target=False,
                        snippet=text[max(0, m.start() - 40):m.end() + 20]))
    for i, a in enumerate(out):                      # "giá X ... giảm Y": X is not the final price
        if a["cls"] in ("positive", "neutral") and i + 1 < len(out) and out[i + 1]["cls"] == "discount":
            gap = re.sub(r"\([^()]*\)", " ", text[a["end"]:out[i + 1]["start"]])   # drop closed (...)
            if len(gap) <= 40 and not re.search(r"[.;!?|\n(]", gap):
                a["cls"], a["demoted"] = "old", True
                if out[i + 1]["value"] >= 0.5 * a["value"]:   # "16,5 tỷ giảm 13,7 tỷ": 13,7 is the new price
                    out[i + 1]["cls"], out[i + 1]["chain_target"] = "positive", True
    for i, a in enumerate(out):                      # "X về Y": X is old, Y is the price
        if a["superseded"] and i + 1 < len(out) and out[i + 1]["start"] - a["end"] <= 30:
            if a["cls"] in ("positive", "neutral"):
                a["cls"] = "old"
            if out[i + 1]["cls"] in ("neutral", "old") and not out[i + 1].get("demoted"):
                out[i + 1]["cls"] = "positive"
            if out[i + 1]["cls"] == "positive":
                out[i + 1]["chain_target"] = True
    return out


def _decide(cands):
    pos = [a for a in cands if a["cls"] == "positive"]
    if pos:
        vals = {round(a["value"], 3) for a in pos}
        if len(vals) == 1 or max(vals) <= min(vals) * 1.01:
            return pos[0]["value"], "keyword", pos[0]["snippet"]
        chain = [a for a in pos if a["chain_target"]]
        if chain:
            return chain[0]["value"], "keyword_chain", chain[0]["snippet"]
        reduced = [a for a in pos if a["kw"] in ("còn", "xuống", "về", "nay", "giá mới", "mới")]
        if reduced and len({round(a["value"], 3) for a in reduced}) == 1:
            return reduced[0]["value"], "keyword_reduced", reduced[0]["snippet"]
        return None, "ambiguous", ""
    neu = [a for a in cands if a["cls"] == "neutral"]
    vals = {round(a["value"], 3) for a in neu}
    if len(vals) == 1:
        return neu[0]["value"], "single_amount", neu[0]["snippet"]
    return None, ("ambiguous" if neu else "no_amount"), ""


def stated_price(title, description):
    """(price in tỷ or None, how, evidence snippet); how is "ambiguous" when a field states several prices."""
    t_amounts = amounts(title)
    t_price, t_how, t_snip = _decide(t_amounts)
    d_price, d_how, d_snip = _decide(amounts(description))
    if t_price is not None:
        # "nhỉnh 7 tỷ" in the title, "nay còn 7,89 tỷ" in the description: the precise figure wins
        t_amt = next((a for a in t_amounts if a["snippet"] == t_snip), None)
        if t_amt and t_amt["approx"] and d_price is not None and 0.8 * t_price <= d_price <= 1.25 * t_price:
            return d_price, f"description:{d_how}", d_snip
        return t_price, f"title:{t_how}", t_snip
    if d_price is not None:
        return d_price, f"description:{d_how}", d_snip
    return None, ("ambiguous" if "ambiguous" in (t_how, d_how) else "none"), ""


def crawler_value(title, description, skip_tr=True):
    """(value, field, amount) — the 2026 crawler's reading: first amount, tail dropped."""
    for field, text in (("title", title), ("description", description)):
        text_n = norm(text)
        for m in AMOUNT.finditer(text_n):
            if skip_tr and m.group("unit").lower() == "tr":
                continue
            v = _value(m, keep_tail=False)
            if v is not None and v > 0:
                a = next(a for a in amounts(text) if a["start"] == m.start())
                return round(v, 4), field, a
    return None, None, None


SELFTEST = [  # (title, description, expected stated price)
    ("Giá chỉ 2 tỷ 3.", "", 2.3), ("Giá 6tỷ9.", "", 6.9), ("giá 6 tỷ 90 triệu", "", 6.09),
    ("Nhà 3tỷ450 hẻm xe hơi", "", 3.45), ("Từ 3 tỷ 800, nay chỉ còn 3 tỷ 500", "", 3.5),
    ("từ 20 - 2000 tỷ", "", None), ("Chủ hạ giá 250 triệu giá mới 2,35 tỷ. Giá cũ 2,6 tỷ", "", 2.35),
    ("Trả trước 708 triệu (30%) nhận nhà", "", None), ("13 triệu/1m² khoảng 16,26 tỷ", "", 16.26),
    ("HĐT 2 tỷ/năm", "", None), ("hầm 7 tầng - thuê 1,5 tỷ/tháng - 350 tỷ", "", 350.0),
    ("Giá 5tỷ 97", "", 5.97), ("HĐT 1 tỷ/năm - chỉ 65 tỷ", "", 65.0),
    ("Giảm sốc 1 tỷ nhà mặt tiền Tam Bình ngang 7m, 174m2 chỉ 17,5 tỷ", "", 17.5),
    ("Có HĐ thuê 1,56tỷ/năm. Sổ hồng. 117 tỷ", "", 117.0),
    ("Nhà Huỳnh Tấn Phát - đang thu nhập 30 triệu - 4x35m Giá 17,5 tỷ", "", 17.5),
    ("Giảm 300 triệu căn hộ Ngô Tất Tố", "", None), ("18tỷ về 15,7tỷ thương lượng", "", 15.7),
    ("Gấp bán 13,9 tỷ giảm về 12,9 tỷ", "", 12.9), ("Giảm mạnh chỉ 3,15 tỷ sở hữu ngay", "", 3.15),
    ("Bán lỗ chỉ 29 tỷ", "", 29.0), ("Giá hạ bán: 7,69 tỷ (giá cũ 8,6 tỷ)", "", 7.69),
    ("CC Wilton Tower, Bình Thạnh: 2PN=6,75 tỷ", "", 6.75), ("Giảm 1.4 tỷ còn 16,5 tỷ", "", 16.5),
    ("Giảm mạnh 4 tỷ về 21 tỷ, nhà đẹp", "", 21.0), ("giảm 20 tỷ còn 108 tỷ", "", 108.0),
    ("Siêu dòng tiền 1,6 tỷ/năm - Bán tòa nhà", "", None), ("Bán nhà 2 tỷ 94 tr", "", 2.094),
    ("HĐT: 22tr/th, giá: 20 tỷ về 17,5 tỷ", "", 17.5), ("căn studio giá gốc 2,1 tỷ bán còn 1,7 tỷ", "", 1.7),
    ("Ngân hàng định giá 7,7 tỷ cho vay 6,2 tỷ", "", None), ("Dòng tiền thu về 30 triệu tháng", "", None),
    ("thấp hơn giá trung bình khu vực 2,4 tỷ", "", None), ("Giá: 6,4 tỷ nay chủ giảm nhanh 200 triệu", "", None),
    ("Chủ giảm chào 1 tỷ - Nhà 3 tầng", "", None), ("Giá hạ bán 12,39 tỷ còn TL nhẹ. - Giá cũ 13 tỷ.", "", 12.39),
    ("Chỉ dưới 5.69 tỷ còn bớt. - Giá cũ 6.6 tỷ.", "", 5.69), ("Ngộp bank để lại 9,8 tỷ hơn 109,5m2", "", 9.8),
    ("+ Tổng giá đã có VAT và phí bảo trì: 2.2 tỷ.", "", 2.2), ("Giá bán: 5,8 tỷ/căn.", "", 5.8),
    ("Giá giảm: 6,2tỷ thương lượng.", "", 6.2), ("Hạ giá từ 7,15 tỷ xuống 6,25 tỷ bao rẻ", "", 6.25),
    ("Mặt tiền C18. CTXD: Hầm 7 tầng. TN: 600tr. VIP", "", None),
    ("Giảm sốc gần 1 tỷ đồng - nhỉnh 7 tỷ hot!", "- Giá cũ: 8.6 tỷ. - Nay hạ còn: 7.89 tỷ thương lượng.", 7.89),
    ("Chỉ 53 triệu/m2 - nhà C4", "Giá bán 6.5 tỷ giảm mạnh 5.7 tỷ.", 5.7),
    ("Cắt lỗ khẩn cấp 500 triệu", "Giá hợp đồng gốc: 4.5 tỷ. Giá cắt lỗ xả hàng: 3.99tỷ (Có thương lượng)", 3.99),
    ("Building 1200m2 sàn, đơn giá quanh 650 triệu/m2", "vùng giá giao dịch thực tế quanh 130 tỷ. - Giá bán: 135 tỷ", 135.0),
    ("Giảm hơn 500 triệu!", "Giá: 8.99 tỷ (thương lượng) giá mới 8.4 tỷ (vẫn còn thương lượng).", 8.4),
    ("Khách sạn 38 phòng đơn giá 913 triệu/m2", "Giá giao dịch thực tế quanh 137 tỷ. Giá bán: 140 tỷ thương lượng.", 140.0),
    ("MTKD HĐT 318 triệu/th", "* Giá chào: 175 tỷ. * Giá kỳ vọng giao dịch: 155 tỷ.", 175.0),
    ("Giảm 1.4 tỷ- MT Nguyễn Văn Lượng", "- Giá bán cuối 11,9tỷ giam còn 11.3ty giảm tiếp 10.5 tỷ TL nhẹ.", 10.5),
    ("Top giá tốt nhà phối xẻ khe MT 9m | sẵn HĐT 360tr/năm", "Giá bán: 18 tỷ total. Giá trị căn thô quy đổi chỉ còn khoảng 16 tỷ.", 18.0),
    ("Nhà", "- Giá cũ bán: 7,15 tỷ. - Nay hạ: 6,25 tỷ. Hạ giá từ 7,15 tỷ xuống 6,25 tỷ", 6.25),
    ("Tòa nhà", "Giá cũ 36,8 tỷ giảm 4 tỷ chỉ còn 32,8 tỷ. HĐT 4,5 tỷ. Giá trị tăng thêm ~16,4 tỷ.", 32.8),
    ("Giảm 1 tỷ, nhà phố", "- Giá bán cạnh tranh: 7.19 tỷ. - Hạ giá bán chỉ còn 6,09 tỷ.", 6.09),
    ("Nhà", "+ Giá: 11.8 tỷ (đã giảm 5 tỷ giá cũ 16.8 tỷ).", 11.8),
    ("Giảm gần 3 tỷ!", "- Giá: 16.5 tỷ (còn TL) giảm 13,7 tỷ (thương lượng mạnh.", 13.7), ("Nhà phố", "Giá bán: 9 tỷ 150 triệu cực hấp dẫn", 9.15),
]


def selftest():
    bad = 0
    for t, d, want in SELFTEST:
        got = stated_price(t, d)[0]
        ok = (got is None and want is None) or (got is not None and want is not None and abs(got - want) < 1e-6)
        if not ok:
            bad += 1
            print(f"FAIL {t!r}: got {got}, want {want}  {[(a['value'], a['cls']) for a in amounts(t)]}")
    print(f"selftest: {len(SELFTEST) - bad}/{len(SELFTEST)} ok")
    return bad == 0


if __name__ == "__main__":
    raise SystemExit(0 if selftest() else 1)
