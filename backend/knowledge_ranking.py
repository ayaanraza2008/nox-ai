"""Small deterministic relevance helpers for NOX knowledge retrieval."""
import re


def rank_knowledge_candidates(query: str, rows: list[dict]) -> list[dict]:
    """Rank lexical candidates using token coverage, title matches, and phrase matches."""
    terms = list(dict.fromkeys(t.casefold() for t in re.findall(r"[\w\u0900-\u097f\u0600-\u06ff]+", query) if len(t) > 1))
    phrase = re.sub(r"\s+", " ", query.casefold()).strip()
    scored = []
    for row in rows:
        title = str(row.get("title") or "").casefold()
        body = str(row.get("content") or row.get("text") or "").casefold()
        combined = title + " " + body
        matched = {term for term in terms if term in combined}
        if not matched:
            continue
        score = sum(min(body.count(term), 4) * (2.5 if len(term) > 4 else 1.0) for term in terms)
        score += sum(3.0 if len(term) > 3 else 1.5 for term in matched if term in title)
        score += 5.0 * len(matched) / max(1, len(terms))
        if phrase and phrase in combined:
            score += 7.0
        item = dict(row)
        item["relevance"] = round(len(matched) / max(1, len(terms)), 3)
        scored.append((score, str(row.get("updated_at") or ""), item))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item for _, _, item in scored]
