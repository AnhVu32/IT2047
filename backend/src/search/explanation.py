from __future__ import annotations

from typing import List

from src.search.schemas import ParsedSearchQuery


def build_evidence(item: dict, parsed: ParsedSearchQuery) -> dict:
    matched: List[str] = []
    preference_notes: List[str] = []
    hard = parsed.hard_filters
    preferred = parsed.preference_filters
    if hard.price.max is not None:
        matched.append(f"Giá {item.get('price_range')} tỷ, không vượt ngân sách {hard.price.max:g} tỷ")
    if hard.price.min is not None:
        matched.append(f"Giá từ {hard.price.min:g} tỷ")
    if hard.area.min is not None:
        matched.append(f"Diện tích {item.get('area')} m², đạt tối thiểu {hard.area.min:g} m²")
    if hard.bedrooms.min is not None:
        matched.append(f"Có {item.get('bedrooms')} phòng ngủ")
    if hard.districts:
        matched.append(f"Thuộc {item.get('district')}")
    if preferred.price.target is not None:
        preference_notes.append(
            f"Giá {item.get('price_range')} tỷ so với mức mong muốn {preferred.price.target:g} tỷ"
        )
    elif preferred.price.max is not None:
        preference_notes.append(
            f"Giá {item.get('price_range')} tỷ so với ngân sách mong muốn {preferred.price.max:g} tỷ"
        )
    if preferred.area.target is not None or preferred.area.min is not None:
        desired = preferred.area.target if preferred.area.target is not None else preferred.area.min
        preference_notes.append(f"Diện tích {item.get('area')} m² so với mong muốn {desired:g} m²")
    if preferred.districts or preferred.former_admin_areas:
        actual = item.get("district") or item.get("former_admin_area")
        requested = ", ".join((*preferred.districts, *preferred.former_admin_areas))
        if item.get("score_breakdown", {}).get("location") == 1.0:
            preference_notes.append(f"Đúng khu vực ưu tiên: {actual}")
        else:
            preference_notes.append(f"Ngoài khu vực ưu tiên {requested}: {actual}")
    for feature in hard.required_features:
        if item.get(feature):
            matched.append(f"Có tiện ích {feature}")
    graph_evidence = []
    for evidence in item.get("amenity_evidence") or []:
        if evidence.get("driving_distance_km") is not None:
            graph_evidence.append(
                f"{evidence.get('category')} gần nhất cách {float(evidence['driving_distance_km']):.1f} km"
            )
    neo4j_evidence = item.get("graph_evidence") or {}
    for evidence in neo4j_evidence.get("amenities") or []:
        distance = evidence.get("driving_distance_km")
        if distance is not None:
            graph_evidence.append(
                f"Neo4j xác nhận {evidence.get('category')} {evidence.get('name') or ''} "
                f"cách {float(distance):.1f} km".strip()
            )
    for ward in neo4j_evidence.get("wards") or []:
        graph_evidence.append(f"Neo4j xác nhận thuộc khu vực {ward}")
    semantic = []
    score = item.get("score_breakdown", {}).get("semantic", 0)
    if score > .5:
        semantic.append(f"Nội dung tin phù hợp ngữ nghĩa truy vấn (điểm {score:.2f})")
    return {
        "matched_constraints": matched,
        "preference_evidence": preference_notes,
        "amenity_evidence": graph_evidence,
        "semantic_evidence": semantic,
    }


def attach_explanation(item: dict, parsed: ParsedSearchQuery) -> dict:
    evidence = build_evidence(item, parsed)
    facts = (
        evidence["matched_constraints"]
        + evidence["preference_evidence"]
        + evidence["amenity_evidence"]
        + evidence["semantic_evidence"]
    )
    item["matched_criteria"] = evidence["matched_constraints"]
    item["evidence"] = evidence
    item["explanation"] = ". ".join(facts[:5]) + ("." if facts else "")
    return item
