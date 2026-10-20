"""Small deterministic relevance helpers for NOX knowledge retrieval."""
import re


_TOKEN_RE = re.compile(r"[\w\u0900-\u097f\u0600-\u06ff]+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(value or "")]


def _term_matches(term: str, tokens: set[str]) -> bool:
    # Exact token matches prevent false positives such as "art" in "partial".
    # Prefix matches retain useful lexical behavior for incomplete words.
    return term in tokens or (len(term) >= 4 and any(token.startswith(term) for token in tokens))


def rank_knowledge_candidates(query: str, rows: list[dict]) -> list[dict]:
    """Rank candidates using token coverage, title matches, and phrase matches."""
    terms = list(dict.fromkeys(t for t in _tokens(query) if len(t) > 1))
    phrase = re.sub(r"\s+", " ", query.casefold()).strip()
    scored = []
    for row in rows:
        title = str(row.get("title") or "")
        body = str(row.get("content") or row.get("text") or "")
        title_tokens = set(_tokens(title))
        body_tokens = set(_tokens(body))
        all_tokens = title_tokens | body_tokens
        matched = {term for term in terms if _term_matches(term, all_tokens)}
        semantic_similarity = float(row.get("semantic_similarity") or 0.0)
        if not matched and semantic_similarity < 0.15:
            continue

        score = 10.0 * semantic_similarity
        for term in terms:
            if _term_matches(term, body_tokens):
                score += min(sum(1 for token in body_tokens if token == term or
                                 (len(term) >= 4 and token.startswith(term))), 4) * (2.5 if len(term) > 4 else 1.0)
            if _term_matches(term, title_tokens):
                score += 3.0 if len(term) > 3 else 1.5
        score += 5.0 * len(matched) / max(1, len(terms))
        normalized_combined = re.sub(r"\s+", " ", (title + " " + body).casefold()).strip()
        if phrase and phrase in normalized_combined:
            score += 7.0
        item = dict(row)
        item["relevance"] = round(max(len(matched) / max(1, len(terms)), semantic_similarity), 3)
        scored.append((score, str(row.get("updated_at") or ""), item))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item for _, _, item in scored]
