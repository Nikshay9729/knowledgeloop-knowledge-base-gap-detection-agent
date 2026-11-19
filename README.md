# KnowledgeLoop

KnowledgeLoop finds recurring support issues that have no knowledge article, flags articles that conflict with recent resolutions or apply to an older product version, and prepares evidence-backed drafts for expert review.

## Run locally

```powershell
cd outputs/knowledgeloop
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Open <http://127.0.0.1:8000>. The included demo dataset shows an MFA article gap and two stale-article flags. The first run loads the sample data from `data/demo.json`; actions and review state are saved in `data/workspace.json`.

## Data format

Import one JSON file with `tickets` and `articles` arrays. Tickets can include `id`, `issue_key`, `subject`, `symptoms`, `cause`, `steps`, `verification`, `resolution_notes`, `product_version`, and `resolved_at`. Articles can include `id`, `issue_key`, `title`, `body`, `product_version`, `last_reviewed`, and optional `conflict_pairs`.

The local prototype uses supplied issue keys when available and keyword similarity otherwise. Recurrence threshold is three tickets. Version mismatch and explicit `conflict_pairs` drive stale flags. Draft fields are collected from the ticket records; when only unstructured resolution notes are available, the notes are preserved as evidence and the expert should complete the structured fields before approving.

## Review and indexing

Drafts stay in `pending_review` until an expert edits the structured fields and approves them. The API only calls ChromaDB after approval. ChromaDB is persistent under `data/chroma`, and the prototype uses deterministic local hashed embeddings so indexing does not download a model. This embedding approach keeps the demo self-contained; replace it with your production embedding model before using it for retrieval at scale.

If ChromaDB is unavailable, approval is retained as `approved_index_unavailable`; install the listed dependencies and use **Retry indexing**. Unapproved drafts cannot be indexed.

## Prototype limits

Clustering and article matching are deterministic keyword heuristics, not semantic model decisions. Review the evidence and stale flags before publishing. The app is designed to make the approval gate and data flow reviewable, not to replace expert judgment.
