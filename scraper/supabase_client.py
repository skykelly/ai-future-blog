"""
supabase_client.py
Life After AI — Supabase REST API client for scraper
Reads SUPABASE_URL / SUPABASE_SERVICE_KEY from environment.
"""

import logging
import os
import requests

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")


def is_configured() -> bool:
    return bool(SUPABASE_URL and SERVICE_KEY)


def _headers(extra: dict = None) -> dict:
    h = {
        "apikey":        SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h


def get_existing_urls() -> set:
    """Return set of article URLs already in Supabase."""
    if not is_configured():
        return set()
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/articles?select=url",
            headers=_headers(),
            timeout=15,
        )
        if resp.ok:
            return {r["url"] for r in resp.json() if r.get("url")}
        log.warning(f"Supabase URL fetch failed: {resp.status_code}")
    except Exception as e:
        log.warning(f"Supabase get_existing_urls error: {e}")
    return set()


def get_total_count() -> int:
    """Return total article count from Supabase."""
    if not is_configured():
        return 0
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/articles?select=id",
            headers={**_headers(), "Prefer": "count=exact"},
            timeout=10,
        )
        if resp.ok:
            return int(resp.headers.get("Content-Range", "0/0").split("/")[-1])
    except Exception as e:
        log.warning(f"Supabase count error: {e}")
    return 0


def insert_articles(cases: list) -> dict:
    """
    Upsert articles into Supabase.
    Skips existing IDs (resolution=ignore-duplicates).
    Returns {"inserted": n, "skipped": m}.
    """
    if not is_configured() or not cases:
        return {"inserted": 0, "skipped": len(cases)}

    rows = [_map_case(c) for c in cases]
    headers = _headers({"Prefer": "resolution=ignore-duplicates,return=minimal"})

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/articles",
            headers=headers,
            json=rows,
            timeout=30,
        )
        if resp.ok:
            log.info(f"Supabase insert OK: {len(rows)}개 처리")
            return {"inserted": len(rows), "skipped": 0}
        else:
            log.error(f"Supabase insert failed: {resp.status_code} — {resp.text[:300]}")
            return {"inserted": 0, "skipped": len(rows)}
    except Exception as e:
        log.error(f"Supabase insert error: {e}")
        return {"inserted": 0, "skipped": len(rows)}


def _map_case(c: dict) -> dict:
    """Map cases.json field names → Supabase articles table columns."""
    return {
        "id":             c["id"],
        "category_id":    c.get("category"),
        "company":        c.get("company", ""),
        "short":          c.get("short"),
        "color_bg":       c.get("color_bg"),
        "color_text":     c.get("color_text"),
        "kpi_value":      c.get("kpi_value"),
        "kpi_label":      c.get("kpi_label"),
        "title":          c.get("title", ""),
        "description":    c.get("description"),
        "body":           c.get("body"),
        "metrics":        c.get("metrics", []),
        "tags":           c.get("tags", []),
        "source":         c.get("source"),
        "url":            c.get("url"),
        "published_date": c.get("published_date") or None,
        "added_date":     c.get("added_date") or None,
        "verified":       c.get("verified", False),
    }
