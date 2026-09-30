"""Client LLM tuỳ chọn (provider-agnostic, tương thích OpenAI API).

Mặc định TẮT -> pipeline chạy offline hoàn toàn bằng template + RNG. Bật bằng:

    export USE_LLM=1
    export GROQ_API_KEY=gsk_...        # hoặc LLM_API_KEY
    # (tuỳ chọn) LLM_MODEL, LLM_BASE_URL, LLM_PROVIDER

Provider mặc định = Groq (nhanh, rẻ). Vì Groq/Grok/OpenAI đều tương thích API
OpenAI nên chỉ cần đổi base_url + model + key qua .env là chuyển provider.

Nguyên tắc: **LLM chỉ lo phần VĂN BẢN** (câu truy vấn tự nhiên, persona, mô tả).
Phân phối/nhãn vẫn do RNG có seed kiểm soát (xem generate_*.py). Mọi lời gọi LLM
đều có fallback template/None nếu lỗi -> không bao giờ làm hỏng pipeline.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

import numpy as np

# Preset provider tương thích OpenAI
_PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile",
             ("GROQ_API_KEY", "LLM_API_KEY")),
    "grok": ("https://api.x.ai/v1", "grok-3-mini", ("XAI_API_KEY", "LLM_API_KEY")),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini", ("OPENAI_API_KEY", "LLM_API_KEY")),
}


def _load_dotenv_once():
    """Nạp biến từ .env (gốc dự án) vào os.environ nếu chưa set. Không cần
    python-dotenv — parse tay KEY=VALUE, bỏ comment/blank. Chạy 1 lần."""
    if os.environ.get("_GENDATA_DOTENV_LOADED"):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    path = os.path.join(root, ".env")
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    v = v.split(" #")[0].strip()        # cắt comment inline "VALUE # ..."
                    v = v.strip('"').strip("'")
                    os.environ.setdefault(k.strip(), v)  # không ghi đè biến đã export
        except Exception:
            pass
    os.environ["_GENDATA_DOTENV_LOADED"] = "1"


_load_dotenv_once()


def _first_env(*names) -> Optional[str]:
    for n in names:
        v = os.getenv(n)
        if v and v.strip():
            return v.strip()
    return None


class LLMClient:
    """Bọc SDK `openai` trỏ tới endpoint tương thích OpenAI (Groq mặc định)."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        base_default, model_default, key_names = _PROVIDERS.get(
            self.provider, _PROVIDERS["groq"])
        self.base_url = os.getenv("LLM_BASE_URL", base_default)
        self.model = os.getenv("LLM_MODEL", model_default)
        self.api_key = _first_env(*key_names)
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.8"))
        self._want = os.getenv("USE_LLM", "0") == "1"
        self._client = None
        self._init_error: Optional[str] = None
        if self._want:
            self._try_init()

    def _try_init(self):
        if not self.api_key:
            self._init_error = "thiếu API key (GROQ_API_KEY / LLM_API_KEY)"
            return
        try:
            from openai import OpenAI  # SDK tương thích mọi provider OpenAI-like
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        except Exception as e:  # pragma: no cover - phụ thuộc môi trường
            self._init_error = f"không khởi tạo được client ({e})"

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def status(self) -> str:
        if not self._want:
            return "LLM OFF (USE_LLM!=1) -> dùng template/RNG"
        if self.enabled:
            return f"LLM ON: provider={self.provider} model={self.model}"
        return f"LLM yêu-cầu-bật nhưng KHÔNG dùng được: {self._init_error} -> fallback template"

    def complete(self, system: str, user: str, max_tokens: int = 1500) -> Optional[str]:
        if not self.enabled:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model, temperature=self.temperature,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            return resp.choices[0].message.content
        except Exception as e:  # pragma: no cover
            print(f"[llm] lỗi gọi model, fallback: {e}")
            return None

    def complete_json_list(self, system: str, user: str,
                           max_tokens: int = 2500) -> Optional[List]:
        """Gọi LLM và ép parse ra JSON array. None nếu thất bại."""
        raw = self.complete(system + "\nCHỈ trả về JSON array hợp lệ, không giải thích.",
                            user, max_tokens=max_tokens)
        if not raw:
            return None
        return _extract_json_list(raw)


def _extract_json_list(text: str) -> Optional[List]:
    # bóc ```json ... ``` nếu có
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    candidate = m.group(1) if m else None
    if candidate is None:
        m = re.search(r"(\[.*\])", text, re.S)
        candidate = m.group(1) if m else text
    try:
        val = json.loads(candidate)
        return val if isinstance(val, list) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# QueryGenerator: câu tìm kiếm raw_query (template offline; LLM khi bật)
# ---------------------------------------------------------------------------
# Template có slot {price_word} — từ ngữ mức giá điền theo price_tier_area (tương
# đối trong quận), nên "rẻ/đắt" phản ánh đúng khu vực chứ không phải ngưỡng tuyệt đối.
_TEMPLATES: Dict[str, list] = {
    "buy_for_living": [
        "{ptype} {district} {price_word} cho gia đình",
        "cần mua {ptype} {beds} phòng ngủ ở {district} để ở, {price_word}",
        "tìm {ptype} {district} {price_word} gần trường học",
        "{ptype} {district} {price_word} cho vợ chồng mới cưới",
        "nhà ở {district} thoáng mát {beds}pn, {price_word}",
    ],
    "investment": [
        "{ptype} {district} {price_word} cho thuê lại được",
        "tìm {ptype} {district} {price_word} tiềm năng tăng giá",
        "mua {ptype} đầu tư ở {district} pháp lý rõ ràng, {price_word}",
        "{ptype} {district} {price_word} dòng tiền tốt",
    ],
    "rent": [
        "thuê {ptype} {district} {beds} phòng ngủ {price_word}",
        "cần thuê {ptype} {district} full nội thất, {price_word}",
        "{ptype} {district} {price_word} cho thuê gần metro",
        "tìm phòng {ptype} ở {district} {price_word}",
    ],
}

# Từ ngữ mức giá theo tier tương đối trong khu vực.
_PRICE_WORDS: Dict[str, list] = {
    "cheap": ["giá rẻ", "giá tốt", "bình dân", "rẻ một chút", "giá mềm"],
    "mid": ["giá hợp lý", "tầm trung", "giá vừa phải", "ổn định"],
    "premium": ["cao cấp", "vị trí đẹp", "sang trọng", "khu nhà giàu"],
}
_TIER_HINT_VI = {
    "cheap": "rẻ so với mặt bằng khu vực",
    "mid": "tầm trung so với khu vực",
    "premium": "cao cấp/đắt so với khu vực",
}


class QueryGenerator:
    """Sinh raw_query. Template offline (mặc định) hoặc LLM batch (khi bật).

    Từ ngữ mức giá ("rẻ", "cao cấp"...) lấy theo `price_tier` = mức giá TƯƠNG ĐỐI
    trong quận (cheap/mid/premium), không dùng ngưỡng giá tuyệt đối.
    """

    def __init__(self, seed: int, llm: Optional[LLMClient] = None):
        self.rng = np.random.default_rng(seed)
        self.llm = llm or LLMClient()

    def _price_word(self, tier: Optional[str]) -> str:
        bank = _PRICE_WORDS.get(tier or "mid", _PRICE_WORDS["mid"])
        return str(self.rng.choice(bank))

    # --- template (per-item, offline, luôn có) ---
    def template(self, *, intent: str, district: str, price: float,
                 beds: int, property_type: str, price_tier: Optional[str] = None) -> str:
        templates = _TEMPLATES.get(intent, _TEMPLATES["buy_for_living"])
        t = str(self.rng.choice(templates))
        return t.format(district=district, beds=beds,
                        ptype=property_type.lower(),
                        price_word=self._price_word(price_tier))

    # tương thích ngược với code cũ
    def generate(self, **kw) -> str:
        return self.template(**kw)

    # --- LLM batch (khi bật): nhận list spec, trả list câu ---
    def llm_batch(self, specs: List[Dict]) -> Optional[List[str]]:
        if not self.llm.enabled or not specs:
            return None
        system = (
            "Bạn là người dùng thật đang tìm bất động sản ở Việt Nam. "
            "Với mỗi mục input, viết MỘT câu tìm kiếm tiếng Việt tự nhiên, ngắn, "
            "giọng đời thường (có thể thiếu dấu/viết tắt nhẹ), thể hiện đúng ý định. "
            "Dùng field 'price_hint' để chọn cách nói về giá (vd rẻ/tầm trung/cao cấp) "
            "SO VỚI KHU VỰC — đừng nhắc con số tỷ tuyệt đối. "
            "Trả về JSON array các chuỗi, ĐÚNG thứ tự và ĐÚNG số lượng input."
        )
        user = json.dumps(specs, ensure_ascii=False)
        out = self.llm.complete_json_list(system, user, max_tokens=3000)
        if not out or len(out) != len(specs):
            return None
        return [str(x) for x in out]
