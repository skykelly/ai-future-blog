"""
migrate_categories.py
Supabase categories 테이블 업데이트 + 기존 아티클 category_id 리매핑
실행: python scraper/migrate_categories.py

환경변수 SUPABASE_SERVICE_KEY 필요 (service_role key).
"""

import os
import sys
import json
import urllib.request
import urllib.error

SUPABASE_URL = "https://ectgoceuuunftwuqnixq.supabase.co"
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SERVICE_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY 환경변수가 없습니다.")
    sys.exit(1)

HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

# ── 새 카테고리 정의 ─────────────────────────────────────────────────────────
NEW_CATEGORIES = [
    {"id": "1-1", "area": "Living Space Transformation",        "area_ko": "생활 공간 변화",      "area_type": "space",    "name": "Autonomous Home",          "name_ko": "자율 운영 홈",       "sub": "집이 스스로 환경과 기기를 운영하는 공간"},
    {"id": "1-2", "area": "Living Space Transformation",        "area_ko": "생활 공간 변화",      "area_type": "space",    "name": "Wellness Home",            "name_ko": "웰니스 홈",          "sub": "집이 건강·회복·예방을 관리하는 공간"},
    {"id": "1-3", "area": "Living Space Transformation",        "area_ko": "생활 공간 변화",      "area_type": "space",    "name": "Energy Optimized Home",    "name_ko": "에너지 최적화 홈",   "sub": "AI 에너지 최적화로 생활비를 줄이는 집"},
    {"id": "2-1", "area": "Consumption Transformation",         "area_ko": "소비 행동 변화",      "area_type": "commerce", "name": "Agentic Commerce",         "name_ko": "에이전틱 커머스",    "sub": "AI가 탐색·비교·구매를 대행하는 소비"},
    {"id": "2-2", "area": "Consumption Transformation",         "area_ko": "소비 행동 변화",      "area_type": "commerce", "name": "Service-as-Living",        "name_ko": "생활의 서비스화",    "sub": "제품 소유에서 생활 기능 서비스 이용으로"},
    {"id": "3-1", "area": "Personal Operating Transformation",  "area_ko": "개인 생활 운영 변화", "area_type": "personal", "name": "Personal AI Agent",        "name_ko": "개인 AI 에이전트",   "sub": "개인의 일정·정보·루틴을 조율하는 AI"},
    {"id": "3-2", "area": "Personal Operating Transformation",  "area_ko": "개인 생활 운영 변화", "area_type": "personal", "name": "Hyper-Capability",         "name_ko": "초확장 역량",        "sub": "AI로 업무·학습·창작 역량이 증폭되는 변화"},
    {"id": "4-1", "area": "Relationship & Care Transformation", "area_ko": "관계·돌봄 변화",      "area_type": "care",     "name": "AI Companion",             "name_ko": "AI 동반자",          "sub": "AI가 정서적 대화와 생활 동반자 역할"},
    {"id": "4-2", "area": "Relationship & Care Transformation", "area_ko": "관계·돌봄 변화",      "area_type": "care",     "name": "Remote Senior & Pet Care", "name_ko": "원격 시니어·펫 케어","sub": "시니어·펫 돌봄을 원격·예측형으로"},
]

# 기존 → 신규 category_id 리매핑
REMAP = {
    "2-3": "2-2",
    "3-3": "3-2",
    "4-2": "4-1",
    "4-3": "4-2",
}


def request(method, path, body=None):
    url = SUPABASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def upsert_categories():
    print("\n[1] categories 테이블 upsert...")
    for cat in NEW_CATEGORIES:
        status, resp = request(
            "POST",
            "/rest/v1/categories",
            cat,
        )
        # Prefer: resolution=merge-duplicates 를 추가해야 upsert
        # 위 방식은 새 row만 삽입 — 이미 있으면 conflict. 직접 PATCH로 처리.
    # PATCH 방식으로 모두 업데이트
    for cat in NEW_CATEGORIES:
        cid = cat["id"]
        status, resp = request(
            "PATCH",
            f"/rest/v1/categories?id=eq.{cid}",
            {k: v for k, v in cat.items() if k != "id"},
        )
        if status in (200, 204):
            print(f"  PATCH {cid} OK")
        else:
            # row가 없으면 INSERT
            status2, resp2 = request("POST", "/rest/v1/categories", cat)
            if status2 in (200, 201):
                print(f"  INSERT {cid} OK")
            else:
                print(f"  ERROR {cid}: {status2} {resp2}")


def remap_articles():
    print("\n[2] articles category_id 리매핑...")
    for old_id, new_id in REMAP.items():
        status, resp = request(
            "PATCH",
            f"/rest/v1/articles?category_id=eq.{old_id}",
            {"category_id": new_id},
        )
        if status in (200, 204):
            print(f"  {old_id} → {new_id} OK")
        else:
            print(f"  ERROR {old_id}: {status} {resp}")


def delete_old_categories():
    print("\n[3] 구 카테고리(2-3, 3-3, 4-3) 삭제...")
    for old_id in ["2-3", "3-3", "4-3"]:
        status, resp = request(
            "DELETE",
            f"/rest/v1/categories?id=eq.{old_id}",
        )
        if status in (200, 204):
            print(f"  DELETE {old_id} OK")
        else:
            print(f"  SKIP/ERROR {old_id}: {status} {resp}")


if __name__ == "__main__":
    upsert_categories()
    remap_articles()
    delete_old_categories()
    print("\n완료.")
