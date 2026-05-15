"""
generate_slide_ci.py — GitHub Actions용 슬라이드 생성 스크립트
환경변수로 파라미터를 받아 nlm CLI로 슬라이드를 생성하고
docs/slides/<job_id>.pdf 와 docs/data/slides.json 을 업데이트한다.
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT       = Path(__file__).parent.parent
SLIDES_DIR = ROOT / "docs" / "slides"
SLIDES_JSON = ROOT / "docs" / "data" / "slides.json"
CASES_JSON  = ROOT / "docs" / "data" / "cases.json"

SLIDES_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

CATEGORY_NAMES = {
    "1-1": "Autonomous Home",    "1-2": "Wellness Home",
    "1-3": "Energy Optimized Home",
    "2-1": "Agentic Commerce",   "2-2": "Service-as-Living",
    "3-1": "Personal AI Agent",  "3-2": "Hyper-Capability",
    "4-1": "AI Companion",       "4-2": "Remote Senior & Pet Care",
}

DEFAULT_PROMPT = (
    "업로드된 소스 내용을 바탕으로, 슬라이드 전체를 흥미진진한 만화 형식으로 만들어줘. "
    "각 슬라이드는 개별 만화 컷처럼 레이아웃을 구성하고, 캐릭터들이 대화하는 듯한 형식과 "
    "시각적 효과를 포함해줘. 청중이 영화를 보는 것처럼 느낄 수 있게 해줘."
)


def nlm(*args, timeout=300) -> str:
    cmd = ["nlm"] + [str(a) for a in args]
    log.info("  $ " + " ".join(cmd[:6]))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "nlm 오류")
    return result.stdout.strip()


def parse_notebook_id(text: str) -> str:
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text)
    if not m:
        raise RuntimeError(f"노트북 ID 파싱 실패: {text[:300]}")
    return m.group(1)


def build_research_text(category: str = "") -> str:
    try:
        with open(CASES_JSON, encoding="utf-8") as f:
            db = json.load(f)
        cases = db.get("cases", [])
    except Exception:
        cases = []

    if category:
        filtered = [c for c in cases if c.get("category") == category]
        if not filtered:
            area = category.split("-")[0]
            filtered = [c for c in cases if c.get("category", "").startswith(area + "-")]
        cases = filtered or cases

    lines = ["# Life After AI — 글로벌 AI 생활 변화 리서치 DB\n"]
    lines.append("AI가 고객의 집·소비·개인 생활·관계와 돌봄을 바꾸는 실제 사례 모음.\n")

    grouped = defaultdict(list)
    for c in cases:
        grouped[c.get("category", "기타")].append(c)

    for cat_id, cat_cases in sorted(grouped.items()):
        cat_label = CATEGORY_NAMES.get(cat_id, cat_id)
        lines.append(f"\n## {cat_id} {cat_label}\n")
        for c in cat_cases[:10]:
            lines.append(f"### {c.get('company','')} — {c.get('title','')}")
            lines.append(f"KPI: {c.get('kpi_value','')} {c.get('kpi_label','')}")
            lines.append(c.get("body","") or c.get("description",""))
            metrics = c.get("metrics", [])
            if metrics:
                lines.append("수치: " + " | ".join(f"{m['value']} {m['label']}" for m in metrics[:3]))
            lines.append(f"출처: {c.get('source','')} | {c.get('url','')}\n")

    return "\n".join(lines)[:60000]


def save_slide_meta(meta: dict):
    try:
        existing = json.loads(SLIDES_JSON.read_text(encoding="utf-8"))
    except Exception:
        existing = []
    # 같은 job_id면 덮어쓰기
    existing = [s for s in existing if s.get("id") != meta["id"]]
    existing.insert(0, meta)
    SLIDES_JSON.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    job_id        = os.environ.get("JOB_ID", "ci")
    scenario      = os.environ.get("SCENARIO", "")
    category      = os.environ.get("CATEGORY", "")
    fmt           = os.environ.get("SLIDE_FORMAT", "presenter_slides")
    length        = os.environ.get("SLIDE_LENGTH", "short")
    lang          = os.environ.get("LANG", "ko")
    custom_prompt = os.environ.get("CUSTOM_PROMPT", "") or DEFAULT_PROMPT

    if not scenario:
        log.error("SCENARIO 환경변수가 비어있습니다.")
        sys.exit(1)

    log.info("=" * 60)
    log.info(f"Life After AI — Slide Generation CI  job={job_id}")
    log.info(f"시나리오: {scenario[:80]}")
    log.info(f"카테고리: {category or '전체'} | 형식: {fmt} | 길이: {length} | 언어: {lang}")
    log.info("=" * 60)

    # ── Step 1: 노트북 생성 ────────────────────────────────────────────────────
    log.info("[1/4] NotebookLM 노트북 생성 중...")
    title = f"LAF Slide: {scenario[:48]}{'...' if len(scenario)>48 else ''}"
    nb_out = nlm("notebook", "create", title)
    nb_id  = parse_notebook_id(nb_out)
    nb_url = f"https://notebooklm.google.com/notebook/{nb_id}"
    log.info(f"  Notebook: {nb_id}")

    # ── Step 2: 소스 추가 ─────────────────────────────────────────────────────
    log.info("[2/4] 리서치 DB + 시나리오 소스 추가 중...")
    research = build_research_text(category)
    nlm("source", "add", nb_id, "--text", research,
        "--title", "Life After AI Research DB", "--wait")

    cat_label = CATEGORY_NAMES.get(category, "전체")
    scenario_src = (
        f"# 슬라이드 시나리오\n\n{scenario}\n\n"
        f"카테고리: {category or '전체'} {cat_label}\n"
        f"언어: {'한국어' if lang=='ko' else 'English'}\n\n"
        f"# 스타일 지침\n\n{custom_prompt}"
    )
    nlm("source", "add", nb_id, "--text", scenario_src,
        "--title", "슬라이드 시나리오 및 스타일", "--wait")

    # ── Step 3: 슬라이드 생성 ──────────────────────────────────────────────────
    log.info("[3/4] 슬라이드 생성 요청 중...")
    lang_code  = "ko" if lang == "ko" else "en"
    focus_text = (scenario[:200] + " / " + custom_prompt[:280]).strip()
    nlm("slides", "create", nb_id,
        "--focus",    focus_text,
        "--language", lang_code,
        "--format",   fmt,
        "--length",   length,
        "--confirm",
        timeout=30)

    log.info("[3/4] 슬라이드 완성 대기 중... (최대 6분)")
    for attempt in range(72):
        time.sleep(5)
        try:
            raw  = nlm("status", "artifacts", nb_id, "--json", timeout=30)
            data = json.loads(raw)
            arts = data if isinstance(data, list) else data.get("artifacts", [])
            slide_arts = [
                a for a in arts
                if "slide" in str(a.get("type","")).lower()
                or "slide" in str(a.get("artifact_type","")).lower()
            ]
            if slide_arts:
                status_val = str(slide_arts[0].get("status","")).upper()
                if "COMPLETE" in status_val or "READY" in status_val:
                    log.info(f"  슬라이드 완성 확인 ({attempt*5}초)")
                    break
                if "ERROR" in status_val or "FAIL" in status_val:
                    raise RuntimeError(f"슬라이드 생성 실패: {status_val}")
            log.info(f"  대기 중... {attempt*5}초 경과")
        except json.JSONDecodeError:
            pass
    else:
        raise RuntimeError("슬라이드 생성 시간 초과 (6분)")

    # ── Step 4: PDF 다운로드 ───────────────────────────────────────────────────
    log.info("[4/4] PDF 다운로드 중...")
    pdf_path = SLIDES_DIR / f"{job_id}.pdf"
    nlm("download", "slide-deck", nb_id,
        "--output",      str(pdf_path),
        "--format",      "pdf",
        "--no-progress",
        timeout=120)
    log.info(f"  저장: {pdf_path}")

    # ── 메타데이터 저장 ────────────────────────────────────────────────────────
    slide_meta = {
        "id":          job_id,
        "notebook_id": nb_id,
        "nb_url":      nb_url,
        "title":       scenario[:60] + ("..." if len(scenario)>60 else ""),
        "category":    category or "auto",
        "lang":        lang,
        "format":      fmt,
        "pdf_path":    f"slides/{job_id}.pdf",
        "pdf_url":     f"slides/{job_id}.pdf",
        "createdAt":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_slide_meta(slide_meta)

    log.info("=" * 60)
    log.info("✅ 슬라이드 생성 완료!")
    log.info(f"   NotebookLM: {nb_url}")
    log.info(f"   PDF: docs/slides/{job_id}.pdf")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
