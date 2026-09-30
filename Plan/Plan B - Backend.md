# Plan B — Fallback khu vực trên hệ thống thật (`backend/`)

## Context

Hệ thống search thật hiện **hoàn toàn chưa có** cơ chế fallback khi lọc
`district` trả về rỗng (đã xác minh qua đọc trực tiếp code hiện tại, bản mới
nhất — đã có personalization + impression-logging từ PR đồng nghiệp). Cơ chế
relaxation hiện có trong `service.py::search()` (dòng 89-134) **chỉ** nới
amenity distance/duration và price/area mục tiêu mơ hồ — `district` và
phòng ngủ luôn là filter cứng (SQL `AND`), không bao giờ nới. `relaxations`
được trả về trong response nhưng **không ai đọc**: `llm_answer.py::generate()`
không nhận tham số này, frontend cũng không đọc.

Mục tiêu: khi filter `district` trả về rỗng, hệ thống nới lỏng (giữ nguyên
các tiêu chí khác) thay vì trả 0 kết quả, và trả lời trung thực kiểu:
*"Không tìm thấy Bất động sản phù hợp theo yêu cầu của bạn, nhưng có vài bất
động sản thoả các tiêu chí khác như..., đây là một số bất động sản tôi gợi
ý:..."*

(Xem thêm [`Plan A - Ground Truth.md`](Plan%20A%20-%20Ground%20Truth.md) —
ground truth phía eval được thiết kế theo đúng tinh thần 2 tầng tương tự.
Plan này **độc lập**, không cần chờ Plan A, có thể làm trước.)

---

## `backend/src/search/service.py`
1. Đưa `start = (request.page - 1) * request.top_k` lên sớm hơn (ngay sau
   `started = time.perf_counter()`) — cần dùng làm điều kiện kích hoạt khối
   mới; xoá dòng `start = ...` cũ (hiện ở dòng 142).
2. Thêm khối **district-relaxation** ngay sau khối price/area (dòng 134),
   trước đoạn `user_profile`/`rank_candidates` (dòng 136) — relax khu vực là
   bước rộng nhất nên đặt cuối chuỗi relaxation:
   ```python
   tier1_candidates = candidates
   tier2_candidates: list = []
   district_trial = None
   if (
       not candidates
       and (applied.hard_filters.districts or applied.hard_filters.former_admin_areas)
       and not parsed.protected_constraints
   ):
       district_trial = applied.model_copy(deep=True)
       requested_label = ", ".join(applied.hard_filters.districts + applied.hard_filters.former_admin_areas)
       district_trial.hard_filters.districts = []
       district_trial.hard_filters.former_admin_areas = []
       fallback = await run_in_threadpool(
           search_repository.search, district_trial, query_embedding, candidate_limit
       )
       if fallback:
           tier2_candidates = fallback
           for item in tier2_candidates:
               item["district_relaxed"] = True
           total_candidates = max(total_candidates, len(tier2_candidates))
           relaxations.append(
               f"Không tìm thấy bất động sản tại {requested_label}; "
               f"gợi ý thêm {len(tier2_candidates)} bất động sản ở khu vực khác, "
               f"xếp theo các tiêu chí còn lại"
           )
   ```
   Dùng `not candidates` (khớp đúng 2 khối relaxation sẵn có, đơn giản/an
   toàn cho v1) — đã đủ cho use case "không tìm thấy gì đúng yêu cầu".
3. **Điểm mấu chốt** (đã xác minh là rủi ro thật, không phải giả thuyết):
   `ranker.py:125` — `location = 1.0 if (parsed.hard_filters.districts or ...) else .5`
   và `explanation.py:19-20` — `if hard.districts: matched.append(f"Thuộc {item.get('district')}")`
   — cả 2 chỉ kiểm tra QUERY có filter district hay không, **không** kiểm
   tra TỪNG ITEM có thực sự khớp không. Nếu tầng 2 (item ở khu vực khác) bị
   chấm điểm/giải thích bằng `applied` (còn nguyên filter cũ), nó sẽ bị gán
   sai `location=1.0` và câu "Thuộc {phường/xã}" gây hiểu lầm là khớp yêu
   cầu. → Bắt buộc rank/explain tầng 1 bằng `applied` (còn filter), tầng 2
   bằng `district_trial` (đã xoá filter) — không sửa `ranker.py`/
   `explanation.py`:
   ```python
   ranked = rank_candidates(tier1_candidates, applied, user_profile)
   if tier2_candidates:
       ranked = ranked + rank_candidates(tier2_candidates, district_trial, user_profile)
   selected = diversify(ranked, start + request.top_k)[start:start + request.top_k]
   results = [
       attach_explanation(item, district_trial if item.get("district_relaxed") else applied)
       for item in selected
   ]
   ```
4. Thread `relaxations` vào lời gọi LLM (dòng 149-154): thêm
   `relaxations=relaxations` vào `self.llm_answer.generate(...)`.
5. Fallback tất định khi LLM tắt/không có key (tình huống này đã từng xảy ra
   thật trong phiên làm việc trước — `SEARCH_USE_LLM_ANSWER=false`):
   ```python
   if assistant_answer is None and relaxations and results:
       assistant_answer = (
           "Không tìm thấy bất động sản đúng như yêu cầu của bạn, nhưng có một số "
           "bất động sản khác đáp ứng phần lớn tiêu chí (" + "; ".join(relaxations) +
           "), đây là những gợi ý tôi tìm được."
       )
   ```

## `backend/src/search/llm_answer.py`
1. `generate()` thêm tham số `relaxations: list[str] | None = None` (sau `history`).
2. Đưa vào payload gửi LLM: `"relaxations": relaxations or []`.
3. Thêm `"district_relaxed"` vào tuple `fields` của `_compact_candidate()`
   (dòng 42-58) — để LLM biết item nào là tầng 2.
4. Thêm 1 rule vào `SYSTEM_PROMPT` (dòng 9-34): nếu `relaxations` khác rỗng,
   `answer` phải nêu rõ theo đúng tinh thần: "Không tìm thấy Bất động sản
   phù hợp theo yêu cầu của bạn, nhưng có vài bất động sản thoả các tiêu chí
   khác như..., đây là một số bất động sản tôi gợi ý:..."; với candidate có
   `district_relaxed: true`, `explanation` phải nói rõ căn này KHÔNG thuộc
   khu vực yêu cầu ban đầu.

## `frontend/`
**Không cần sửa.** Đã đọc `frontend/components/ai-chat.tsx` — khi
`results.length > 0`, UI đã hiển thị thẳng `assistant_answer` (hoặc câu mặc
định chung chung nếu rỗng). Một khi `assistant_answer` được điền đúng (qua
LLM hoặc fallback tất định ở bước 5), giao diện tự hiển thị đúng mà không
cần đổi gì. (Ý tưởng thêm badge "Ngoài khu vực yêu cầu" trên `PropertyCard`
là cải tiến tuỳ chọn, không bắt buộc cho mục tiêu hiện tại — để sau.)

---

## Verify
- Test hồi quy hiện có phải pass nguyên: `backend/tests/test_llm_search_answer.py`,
  `backend/tests/test_search_ranker.py`, `backend/tests/test_graph_search.py`,
  `backend/tests/test_search_parser.py`.
- Test mới (theo đúng style `test_llm_search_answer.py` đã có, dùng
  `AsyncMock`/`patch`): `generate(..., relaxations=[...])` có đưa
  `"relaxations"` vào JSON gửi LLM; `_compact_candidate` giữ
  `district_relaxed` khi có.
- Test service-level mới (`IsolatedAsyncioTestCase`, mock
  `search_repository.search/count`, `graph_repository.search`): lần gọi
  `search()` đầu trả 0 dòng đúng khu vực, lần fallback (filter đã xoá) trả
  về N dòng khu vực khác → `relaxations` khác rỗng, `results` toàn bộ có
  `district_relaxed=True`, `assistant_answer` có câu fallback khi LLM tắt.
- Test thủ công: `curl -X POST localhost:8001/v1/search` với 1 phường/xã gần
  như không có listing thoả tiêu chí khác, kiểm tra `relaxations`,
  `results[].district_relaxed`, `assistant_answer` — cả 2 trường hợp
  `SEARCH_USE_LLM_ANSWER=true/false`.
- End-to-end với Plan A: sau khi cả 2 plan + fix `Evaluation/adapters.py`
  xong, chạy lại `Evaluation/run_eval.py --limit 100` — không còn query nào
  rỗng vì lệch khu vực (trước đây im lặng trả 0 dòng, giờ trả kết quả
  fallback).
