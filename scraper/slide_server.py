"""
slide_server.py — Life After AI Slide Generation Server
브라우저 UI와 NotebookLM(nlm CLI)을 연결하는 로컬 HTTP API 서버

Usage:
  python scraper/slide_server.py            # port 8765
  python scraper/slide_server.py --port 9000
"""
import argparse
import json
import logging
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT       = pathlib.Path(__file__).parent.parent
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

# job_id → { status, step, msg, error, pdf_path, nb_id, nb_url }
jobs: dict[str, dict] = {}


# ── nlm subprocess helper ──────────────────────────────────────────────────────

def nlm(*args, timeout=300) -> str:
    cmd = ["nlm"] + [str(a) for a in args]
    log.info("  $ " + " ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def parse_notebook_id(text: str) -> str:
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text)
    if not m:
        raise RuntimeError(f"노트북 ID를 파싱할 수 없음: {text[:200]}")
    return m.group(1)


# ── Research data builder ──────────────────────────────────────────────────────

CATEGORY_NAMES = {
    "1-1": "Autonomous Home",    "1-2": "Wellness Home",
    "1-3": "Energy Optimized Home",
    "2-1": "Agentic Commerce",   "2-2": "Service-as-Living",
    "3-1": "Personal AI Agent",  "3-2": "Hyper-Capability",
    "4-1": "AI Companion",       "4-2": "Remote Senior & Pet Care",
}

AREA_NAMES = {
    "1": "Living Space Transformation (생활 공간 변화)",
    "2": "Consumption Transformation (소비 행동 변화)",
    "3": "Personal Operating Transformation (개인 생활 운영 변화)",
    "4": "Relationship & Care Transformation (관계·돌봄 변화)",
}


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
    lines.append("이 데이터는 AI가 고객의 생활, 소비, 개인 운영, 관계·돌봄을 어떻게 바꾸는지 추적한 글로벌 사례 모음입니다.\n")

    if category:
        cat_name = CATEGORY_NAMES.get(category, category)
        area_name = AREA_NAMES.get(category.split("-")[0], "")
        lines.append(f"## 포커스 카테고리: {category} {cat_name}\n## 영역: {area_name}\n")

    # 카테고리별 그룹핑
    from collections import defaultdict
    grouped = defaultdict(list)
    for c in cases:
        grouped[c.get("category", "기타")].append(c)

    for cat_id, cat_cases in sorted(grouped.items()):
        cat_label = CATEGORY_NAMES.get(cat_id, cat_id)
        lines.append(f"\n## {cat_id} {cat_label}\n")
        for c in cat_cases[:12]:
            lines.append(f"### {c.get('company', '')} — {c.get('title', '')}")
            lines.append(f"KPI: {c.get('kpi_value', '')} {c.get('kpi_label', '')}")
            lines.append(c.get("body", "") or c.get("description", ""))
            metrics = c.get("metrics", [])
            if metrics:
                lines.append("수치: " + " | ".join(f"{m['value']} {m['label']}" for m in metrics[:4]))
            lines.append(f"출처: {c.get('source', '')} {c.get('url', '')}\n")

    return "\n".join(lines)[:60000]


# ── Slide generation job ───────────────────────────────────────────────────────

def run_generation(job_id: str, params: dict):
    scenario    = params.get("scenario", "")
    category    = params.get("category", "")
    slide_count = params.get("slideCount", 12)
    lang        = params.get("lang", "ko")
    fmt         = params.get("format", "detailed_deck")

    def step(n: int, msg: str):
        jobs[job_id].update(step=n, msg=msg, status="running")
        log.info(f"[{job_id}] Step {n}: {msg}")

    def fail(msg: str):
        jobs[job_id].update(status="error", error=msg)
        log.error(f"[{job_id}] ERROR: {msg}")

    try:
        # ── Step 1: 노트북 생성 ────────────────────────────────────────────────
        step(1, "NotebookLM 노트북 생성 중...")
        title_preview = scenario[:48] + ("..." if len(scenario) > 48 else "")
        nb_out = nlm("notebook", "create", f"LAF Slide: {title_preview}")
        nb_id  = parse_notebook_id(nb_out)
        nb_url = f"https://notebooklm.google.com/notebook/{nb_id}"
        jobs[job_id]["nb_id"]  = nb_id
        jobs[job_id]["nb_url"] = nb_url
        log.info(f"[{job_id}] Notebook: {nb_id}")

        # ── Step 2: 리서치 데이터 소스 추가 ────────────────────────────────────
        step(2, "Life After AI 리서치 DB 추가 중...")
        research = build_research_text(category)
        nlm("source", "add", nb_id,
            "--text", research,
            "--title", "Life After AI Research DB",
            "--wait")

        # 시나리오를 별도 소스로 추가
        cat_label = CATEGORY_NAMES.get(category, "전체")
        scenario_src = (
            f"# 슬라이드 생성 시나리오\n\n{scenario}\n\n"
            f"카테고리 포커스: {category or '전체'} {cat_label}\n"
            f"슬라이드 수: {slide_count}장\n"
            f"언어: {'한국어' if lang == 'ko' else 'English'}"
        )
        nlm("source", "add", nb_id,
            "--text", scenario_src,
            "--title", "슬라이드 시나리오",
            "--wait")

        # ── Step 3: 슬라이드 생성 요청 ─────────────────────────────────────────
        step(3, "NotebookLM 슬라이드 생성 중... (1~2분 소요)")
        lang_code = "ko" if lang == "ko" else "en"
        nlm("slides", "create", nb_id,
            "--focus", scenario[:500],
            "--language", lang_code,
            "--format",   fmt,
            "--confirm",
            timeout=30)

        # ── Step 3 (폴링): 완료 대기 ────────────────────────────────────────────
        step(3, "슬라이드 완성 대기 중... (완료까지 1~3분)")
        for attempt in range(72):   # 최대 6분 (5초 × 72)
            time.sleep(5)
            try:
                raw = nlm("status", "artifacts", nb_id, "--json", timeout=30)
                data = json.loads(raw)
                artifacts = data if isinstance(data, list) else data.get("artifacts", [])
                slide_arts = [
                    a for a in artifacts
                    if "slide" in str(a.get("type", "")).lower()
                    or "slide" in str(a.get("artifact_type", "")).lower()
                ]
                if slide_arts:
                    status_val = str(slide_arts[0].get("status", "")).upper()
                    if "COMPLETE" in status_val or "READY" in status_val:
                        break
                    if "ERROR" in status_val or "FAIL" in status_val:
                        raise RuntimeError(f"슬라이드 생성 실패: {status_val}")
                    jobs[job_id]["msg"] = f"슬라이드 생성 중... ({attempt*5}초 경과)"
            except json.JSONDecodeError:
                pass    # 아직 준비 중 — 계속 폴링
        else:
            raise RuntimeError("슬라이드 생성 시간 초과 (6분)")

        # ── Step 4: PDF 다운로드 ────────────────────────────────────────────────
        step(4, "PDF 다운로드 중...")
        pdf_path = SLIDES_DIR / f"{job_id}.pdf"
        nlm("download", "slide-deck", nb_id,
            "--output",      str(pdf_path),
            "--format",      "pdf",
            "--no-progress",
            timeout=120)

        # ── 메타데이터 저장 ─────────────────────────────────────────────────────
        slide_meta = {
            "id":          job_id,
            "notebook_id": nb_id,
            "nb_url":      nb_url,
            "title":       scenario[:60] + ("..." if len(scenario) > 60 else ""),
            "category":    category or "auto",
            "slideCount":  slide_count,
            "lang":        lang,
            "format":      fmt,
            "pdf_path":    f"slides/{job_id}.pdf",
            "createdAt":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _save_slide_meta(slide_meta)

        jobs[job_id].update(
            status   = "done",
            step     = 4,
            msg      = "생성 완료",
            pdf_path = f"slides/{job_id}.pdf",
        )
        log.info(f"[{job_id}] Done → {pdf_path}")

    except Exception as e:
        fail(str(e))


def _save_slide_meta(meta: dict):
    try:
        existing = json.loads(SLIDES_JSON.read_text(encoding="utf-8"))
    except Exception:
        existing = []
    existing.insert(0, meta)
    SLIDES_JSON.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_slides() -> list:
    try:
        return json.loads(SLIDES_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []


# ── HTTP Handler ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: pathlib.Path):
        if not path.exists():
            self._json({"error": "not found"}, 404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/ping":
            self._json({"ok": True})
        elif self.path == "/slides":
            self._json(_load_slides())
        elif self.path.startswith("/status/"):
            job_id = self.path.split("/")[-1]
            self._json(jobs.get(job_id, {"status": "not_found"}))
        elif self.path.startswith("/download/"):
            job_id = self.path.split("/")[-1]
            self._file(SLIDES_DIR / f"{job_id}.pdf")
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/generate":
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length))
        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {
            "status": "pending", "step": 0,
            "msg": "대기 중...", "error": None,
            "pdf_path": None, "nb_id": None, "nb_url": None,
        }
        t = threading.Thread(target=run_generation, args=(job_id, body), daemon=True)
        t.start()
        self._json({"job_id": job_id})

    def log_message(self, *_):
        pass   # suppress default access log


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Life After AI — Slide Generation Server")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    log.info("=" * 56)
    log.info(f"  Life After AI Slide Server — http://localhost:{args.port}")
    log.info(f"  슬라이드 저장 위치: {SLIDES_DIR}")
    log.info("  Ctrl+C 로 종료")
    log.info("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("서버 종료")


if __name__ == "__main__":
    main()
