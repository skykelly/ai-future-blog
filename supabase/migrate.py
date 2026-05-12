"""
migrate.py — cases.json → Supabase migration
Usage:
  export SUPABASE_URL=https://ectgoceuuunftwuqnixq.supabase.co
  export SUPABASE_SERVICE_KEY=eyJ...
  python supabase/migrate.py
"""

import json
import os
import sys
import requests
from pathlib import Path

# .env 파일 로드 (있으면)
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ectgoceuuunftwuqnixq.supabase.co")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SERVICE_KEY:
    print("❌ SUPABASE_SERVICE_KEY가 없습니다.")
    print("   프로젝트 루트에 .env 파일을 만들고 아래 내용을 추가하세요:")
    print("   SUPABASE_SERVICE_KEY=eyJ...")
    sys.exit(1)

HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / "docs" / "data" / "cases.json"


def rest(method: str, table: str, data=None, params=None):
    url  = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = requests.request(method, url, headers=HEADERS, json=data, params=params)
    if not resp.ok:
        print(f"  ❌ {method} {table}: {resp.status_code} — {resp.text[:200]}")
        return False
    return True


def upsert(table: str, rows: list):
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    url     = f"{SUPABASE_URL}/rest/v1/{table}"
    resp    = requests.post(url, headers=headers, json=rows)
    if not resp.ok:
        print(f"  ❌ upsert {table}: {resp.status_code} — {resp.text[:300]}")
        return 0
    return len(rows)


def main():
    with open(DATA_FILE) as f:
        db = json.load(f)

    # ── 1. Categories ─────────────────────────────────────────
    print("▶ categories 마이그레이션...")
    cat_rows = [
        {
            "id":        k,
            "name":      v["name"],
            "sub":       v.get("sub"),
            "area_type": v.get("type"),
            "insight":   v.get("insight"),
        }
        for k, v in db["categories"].items()
    ]
    n = upsert("categories", cat_rows)
    print(f"  ✓ {n}개 categories 완료")

    # ── 2. Articles ───────────────────────────────────────────
    print("▶ articles 마이그레이션...")
    art_rows = []
    for c in db["cases"]:
        art_rows.append({
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
        })

    # 배치 25개씩
    BATCH = 25
    total = 0
    for i in range(0, len(art_rows), BATCH):
        batch = art_rows[i:i+BATCH]
        n = upsert("articles", batch)
        total += n
        print(f"  → {i+len(batch)}/{len(art_rows)} 처리 중...")

    print(f"  ✓ {total}개 articles 완료")
    print("\n✅ 마이그레이션 완료!")


if __name__ == "__main__":
    main()
