"""
batch_add.py
Life After AI — Batch article adder from URL list file

Usage:
  python scraper/batch_add.py urls.txt
  python scraper/batch_add.py urls.txt --delay 3 --dry-run

File format (urls.txt):
  # 카테고리 힌트 없이 (AI 자동 분류)
  https://example.com/article1
  https://example.com/article2

  # 카테고리 힌트와 함께 (쉼표 구분)
  1-1,https://blog.google/ai-home
  2-1,https://mckinsey.com/agentic-commerce
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# .env 로드
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            k, v = _line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

os.chdir(Path(__file__).parent)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("batch_add.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

import requests
from bs4 import BeautifulSoup
from core_scraper import fetch_article_body
from llm_summarizer import extract_case
from supabase_client import is_configured, get_existing_urls, insert_articles


def get_title(url: str) -> str:
    try:
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; LifeAfterAI-Bot/1.0)",
        }, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        og = soup.find("meta", {"property": "og:title"})
        if og and og.get("content"):
            return og["content"].strip()
        t = soup.find("title")
        return t.get_text(strip=True) if t else url
    except Exception as e:
        log.warning(f"제목 조회 실패: {e}")
        return url


def parse_url_file(path: str) -> list[tuple[str, str]]:
    """
    Returns list of (url, category_hint).
    Supports:
      https://...          → ("https://...", "")
      1-1,https://...      → ("https://...", "1-1")
      # comment            → skipped
    """
    entries = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line and not line.startswith("http"):
            hint, url = line.split(",", 1)
            entries.append((url.strip(), hint.strip()))
        else:
            entries.append((line, ""))
    return entries


def process_url(url: str, hint: str, existing_urls: set, dry_run: bool) -> str:
    """
    Process a single URL.
    Returns: 'added' | 'skipped_dup' | 'skipped_no_case' | 'error'
    """
    if url in existing_urls:
        log.info(f"  ⏭  중복 — 건너뜀")
        return "skipped_dup"

    domain = urlparse(url).netloc.replace("www.", "")
    title  = get_title(url)
    body   = fetch_article_body(url)

    if not body:
        log.warning(f"  ❌ 본문 없음")
        return "error"

    article = {
        "title":       title,
        "url":         url,
        "body_text":   body,
        "source_name": domain,
        "source_cats": [hint] if hint else [],
        "summary":     "",
    }

    case = extract_case(article)
    if not case:
        log.info(f"  ⏭  관련 카테고리 없음 — 건너뜀")
        return "skipped_no_case"

    log.info(f"  ✅ [{case['category']}] {case['company']} — {case['title']}")

    if dry_run:
        log.info(f"  (DRY RUN — 저장 안 함)")
        return "added"

    result = insert_articles([case])
    existing_urls.add(url)
    return "added" if result["inserted"] > 0 else "error"


def main():
    parser = argparse.ArgumentParser(description="Life After AI — Batch article adder")
    parser.add_argument("url_file", help="URL 목록 파일 경로")
    parser.add_argument("--delay",   type=float, default=2.0, help="URL 간 대기 시간(초) (기본: 2)")
    parser.add_argument("--dry-run", action="store_true", help="추출만 하고 저장 안 함")
    args = parser.parse_args()

    if not Path(args.url_file).exists():
        log.error(f"파일 없음: {args.url_file}")
        sys.exit(1)

    if not is_configured() and not args.dry_run:
        log.error("SUPABASE_URL / SUPABASE_SERVICE_KEY 환경변수가 없습니다.")
        log.error("  .env 파일을 확인하거나 --dry-run 옵션을 사용하세요.")
        sys.exit(1)

    entries = parse_url_file(args.url_file)
    total   = len(entries)

    log.info("=" * 60)
    log.info(f"Life After AI Batch Add — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"파일: {args.url_file}  |  총 {total}개 URL  |  {'DRY RUN' if args.dry_run else 'LIVE'}")
    log.info("=" * 60)

    existing_urls = get_existing_urls() if is_configured() else set()
    log.info(f"기존 아티클 {len(existing_urls)}개 로드 완료\n")

    stats = {"added": 0, "skipped_dup": 0, "skipped_no_case": 0, "error": 0}
    start = time.time()

    for i, (url, hint) in enumerate(entries, 1):
        log.info(f"[{i}/{total}] {url[:80]}" + (f"  (힌트: {hint})" if hint else ""))
        try:
            result = process_url(url, hint, existing_urls, args.dry_run)
            stats[result] += 1
        except Exception as e:
            log.error(f"  ❌ 처리 오류: {e}")
            stats["error"] += 1

        if i < total:
            time.sleep(args.delay)

    elapsed = time.time() - start
    log.info("\n" + "=" * 60)
    log.info(f"완료 ({elapsed/60:.1f}분)")
    log.info(f"  ✅ 추가됨:        {stats['added']}")
    log.info(f"  ⏭  중복 건너뜀:  {stats['skipped_dup']}")
    log.info(f"  ⏭  해당 없음:    {stats['skipped_no_case']}")
    log.info(f"  ❌ 오류:          {stats['error']}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
