"""KnowledgeLoop local prototype API.

Run with: uvicorn app:app --reload
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STATE_PATH = DATA / "workspace.json"
DEMO_PATH = DATA / "demo.json"

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were", "with", "after", "when", "we", "user", "users", "ticket", "issue", "support", "customer", "unable", "cannot", "not", "use", "using", "into", "their", "they", "has", "have", "had", "then", "also", "can", "could", "should", "will", "would", "only", "same", "new", "old", "please", "resolved", "resolution", "notes", "steps", "verify", "verified", "symptoms", "cause"
}


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(fallback)


def write_state(state: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_state() -> dict[str, Any]:
    return read_json(STATE_PATH, read_json(DEMO_PATH, {"tickets": [], "articles": [], "analysis": None, "drafts": []}))


def tokens(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", value.lower()) if len(word) > 2 and word not in STOP}


def article_text(article: dict[str, Any]) -> str:
    return " ".join([str(article.get("title", "")), str(article.get("body", "")), str(article.get("issue_key", ""))])


def ticket_text(ticket: dict[str, Any]) -> str:
    return " ".join([str(ticket.get("subject", "")), str(ticket.get("symptoms", "")), str(ticket.get("cause", "")), str(ticket.get("resolution_notes", "")), " ".join(ticket.get("steps", []))])


def similarity(left: str, right: str) -> float:
    a, b = tokens(left), tokens(right)
    return len(a & b) / max(1, len(a | b))


def version_tuple(value: str) -> tuple[int, ...]:
    found = re.findall(r"\d+", str(value))
    return tuple(map(int, found)) if found else ()


def clusters_for(tickets: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group by supplied issue_key, then greedily group unlabelled tickets by subject similarity."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unlabeled: list[dict[str, Any]] = []
    for ticket in tickets:
        key = str(ticket.get("issue_key", "")).strip()
        (groups[key] if key else unlabeled).append(ticket)
    clusters = list(groups.values())
    for ticket in unlabeled:
        candidates = [(similarity(str(ticket.get("subject", "")), str(group[0].get("subject", ""))), group) for group in clusters]
        best_score, best_group = max(candidates, key=lambda pair: pair[0], default=(0.0, None))
        if best_group is not None and best_score >= 0.28:
            best_group.append(ticket)
        else:
            clusters.append([ticket])
    return clusters


def unique_values(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        clean = str(item).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def make_draft(cluster: list[dict[str, Any]], issue_key: str) -> dict[str, Any]:
    subjects = unique_values([str(t.get("symptoms") or t.get("subject", "")) for t in cluster])
    causes = unique_values([str(t.get("cause", "")) for t in cluster])
    steps = unique_values([step for t in cluster for step in (t.get("steps") or [])])
    verification = unique_values([str(t.get("verification", "")) for t in cluster])
    # If the source ticket is unstructured, preserve the exact note as evidence rather than infer a fix.
    raw_notes = unique_values([str(t.get("resolution_notes", "")) for t in cluster])
    if not steps and raw_notes:
        steps = [f"Review the recorded resolution: {note}" for note in raw_notes]
    return {
        "id": f"draft-{re.sub(r'[^a-z0-9]+', '-', issue_key.lower()).strip('-') or hashlib.md5('|'.join(str(t.get('id', '')) for t in cluster).encode()).hexdigest()[:8]}",
        "issue_key": issue_key,
        "title": subjects[0] if subjects else f"Troubleshoot {issue_key.replace('-', ' ')}",
        "symptoms": subjects,
        "cause": causes,
        "steps": steps,
        "verification": verification,
        "evidence": [{"ticket_id": str(t.get("id", "unknown")), "resolved_at": t.get("resolved_at", ""), "resolution_notes": t.get("resolution_notes", "")} for t in cluster],
        "status": "pending_review",
        "indexed_at": None,
    }


def analyze(state: dict[str, Any]) -> dict[str, Any]:
    tickets = state.get("tickets", [])
    articles = state.get("articles", [])
    ticket_groups = clusters_for(tickets)
    rows: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []
    stale_flags: list[dict[str, Any]] = []
    for cluster in ticket_groups:
        issue_key = str(cluster[0].get("issue_key") or re.sub(r"[^a-z0-9]+", "-", str(cluster[0].get("subject", "issue")).lower()).strip("-"))
        combined = " ".join(ticket_text(t) for t in cluster)
        candidates = []
        for article in articles:
            has_issue_keys = any(t.get("issue_key") for t in cluster)
            explicit = bool(article.get("issue_key") and has_issue_keys and all(not t.get("issue_key") or t.get("issue_key") == article.get("issue_key") for t in cluster))
            text_score = max((similarity(ticket_text(t), article_text(article)) for t in cluster), default=0.0)
            score = 1.0 if explicit else text_score
            if score >= 0.12:
                candidates.append((score, article))
        best = max(candidates, key=lambda item: item[0], default=(0.0, None))[1]
        recurring = len(cluster) >= 3
        row = {
            "issue_key": issue_key,
            "issue": str(cluster[0].get("symptoms") or cluster[0].get("subject", "Recurring support issue")),
            "ticket_count": len(cluster),
            "ticket_ids": [str(t.get("id", "unknown")) for t in cluster],
            "latest_ticket": max((str(t.get("resolved_at", "")) for t in cluster), default=""),
            "article_id": best.get("id") if best else None,
            "article_title": best.get("title") if best else None,
            "match_score": round(max((s for s, a in candidates if a is best), default=0.0), 2),
            "status": "covered",
            "evidence": [str(t.get("resolution_notes", "")) for t in cluster if t.get("resolution_notes")],
        }
        if recurring and best is None:
            row["status"] = "gap"
            drafts.append(make_draft(cluster, issue_key))
        elif best is not None:
            ticket_versions = [version_tuple(str(t.get("product_version", ""))) for t in cluster]
            article_version = version_tuple(str(best.get("product_version", "")))
            newer_tickets = bool(article_version and any(v and v > article_version for v in ticket_versions))
            combined_low = combined.lower()
            body_low = article_text(best).lower()
            conflict_pairs = best.get("conflict_pairs", [])
            text_conflicts = any((pair.get("article", "").lower() in body_low and pair.get("resolution", "").lower() in combined_low) for pair in conflict_pairs)
            stale = newer_tickets or text_conflicts
            if stale:
                row["status"] = "stale"
                reasons = []
                if newer_tickets:
                    max_version = max((v for v in ticket_versions if v), default=())
                    reasons.append(f"Article covers v{best.get('product_version')}; recent tickets are on v{'.'.join(map(str, max_version))}.")
                if text_conflicts:
                    reasons.append("Recent resolution notes conflict with a claim in this article.")
                flag = {"article_id": best.get("id"), "article_title": best.get("title"), "issue_key": issue_key, "ticket_ids": row["ticket_ids"], "reasons": reasons, "status": "review_needed"}
                stale_flags.append(flag)
                row["stale_reasons"] = reasons
        rows.append(row)
    # Keep previously reviewed drafts and their approval/index state when rerunning analysis.
    previous = {d.get("issue_key"): d for d in state.get("drafts", [])}
    for draft in drafts:
        old = previous.get(draft["issue_key"])
        if old and old.get("status") in ("approved", "indexed", "approved_index_unavailable"):
            draft.update({k: old.get(k) for k in ("status", "indexed_at", "index_message", "approved_by", "approved_at") if k in old})
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "ticket_count": len(tickets),
        "article_count": len(articles),
        "cluster_count": len(rows),
        "gap_count": len(drafts),
        "stale_count": len(stale_flags),
        "clusters": rows,
        "stale_flags": stale_flags,
    }, drafts


def embed_local(text: str, dimensions: int = 384) -> list[float]:
    """Small deterministic local embedding so Chroma needs no network model download."""
    vector = [0.0] * dimensions
    for token in tokens(text):
        raw = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(raw[:4], "big") % dimensions
        sign = 1.0 if raw[4] & 1 else -1.0
        vector[index] += sign
    norm = sum(value * value for value in vector) ** 0.5
    return [value / norm for value in vector] if norm else vector


def index_in_chroma(draft: dict[str, Any]) -> str:
    try:
        import chromadb  # optional until an approved draft is indexed
    except ImportError:
        raise RuntimeError("ChromaDB is not installed. Run `pip install -r requirements.txt` to enable indexing.")
    client = chromadb.PersistentClient(path=str(DATA / "chroma"))
    collection = client.get_or_create_collection(name="knowledge_articles", metadata={"hnsw:space": "cosine"})
    document = "\n".join([
        f"Title: {draft.get('title', '')}",
        f"Symptoms: {'; '.join(draft.get('symptoms', []))}",
        f"Cause: {'; '.join(draft.get('cause', []))}",
        f"Steps: {'; '.join(draft.get('steps', []))}",
        f"Verification: {'; '.join(draft.get('verification', []))}",
    ])
    collection.upsert(
        ids=[draft["id"]],
        documents=[document],
        metadatas=[{"article_id": draft["id"], "issue_key": draft.get("issue_key", ""), "approved": True, "approved_at": draft.get("approved_at", "")}],
        embeddings=[embed_local(document)],
    )
    return "Indexed in local ChromaDB collection knowledge_articles."


app = FastAPI(title="KnowledgeLoop", version="0.1.0")
app.mount("/assets", StaticFiles(directory=ROOT), name="assets")


class ImportPayload(BaseModel):
    tickets: list[dict[str, Any]]
    articles: list[dict[str, Any]]


class ApprovalPayload(BaseModel):
    approved_by: str = "Support expert"
    title: str
    symptoms: list[str]
    cause: list[str]
    steps: list[str]
    verification: list[str]


@app.get("/")
def home() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/api/state")
def state_endpoint() -> dict[str, Any]:
    return get_state()


@app.post("/api/analyze")
def analyze_endpoint() -> dict[str, Any]:
    state = get_state()
    report, drafts = analyze(state)
    state["analysis"], state["drafts"] = report, drafts
    write_state(state)
    return state


@app.post("/api/import")
def import_endpoint(payload: ImportPayload) -> dict[str, Any]:
    state = {"tickets": payload.tickets, "articles": payload.articles, "analysis": None, "drafts": []}
    write_state(state)
    return state


@app.post("/api/drafts/{draft_id}/approve")
def approve_endpoint(draft_id: str, payload: ApprovalPayload) -> dict[str, Any]:
    state = get_state()
    draft = next((item for item in state.get("drafts", []) if item.get("id") == draft_id), None)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found. Run analysis first.")
    draft.update(payload.model_dump())
    draft["status"] = "approved"
    draft["approved_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
    try:
        draft["index_message"] = index_in_chroma(draft)
        draft["status"] = "indexed"
        draft["indexed_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
    except Exception as error:  # approval remains recorded; indexing can be retried after setup
        draft["status"] = "approved_index_unavailable"
        draft["index_message"] = str(error)
    write_state(state)
    return state


@app.post("/api/drafts/{draft_id}/index")
def retry_index_endpoint(draft_id: str) -> dict[str, Any]:
    state = get_state()
    draft = next((item for item in state.get("drafts", []) if item.get("id") == draft_id), None)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    if draft.get("status") not in ("approved", "approved_index_unavailable"):
        raise HTTPException(status_code=409, detail="Only expert-approved drafts can be indexed.")
    try:
        draft["index_message"] = index_in_chroma(draft)
        draft["status"] = "indexed"
        draft["indexed_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
    except Exception as error:
        draft["index_message"] = str(error)
        draft["status"] = "approved_index_unavailable"
    write_state(state)
    return state


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
