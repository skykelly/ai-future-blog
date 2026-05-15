# Life After AI — 단계별 재현 가이드

> Claude Code로 AI 생활 변화 리서치 블로그를 처음부터 만드는 최적 경로.  
> 각 Stage는 독립적으로 실행 가능하며, 순서대로 진행합니다.

---

## 전제 조건 (사전 준비)

| 항목 | 내용 |
|---|---|
| GitHub 레포 | Pages 활성화 (`main` 브랜치 `/docs` 폴더) |
| Supabase 프로젝트 | URL + anon key + service_role key 확보 |
| NotebookLM 계정 | `nlm` CLI 설치 및 로그인 완료 |
| `.env` 파일 | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` 설정 |
| Python | 3.11+, `notebooklm-mcp-cli`, `requests`, `beautifulsoup4` |

```bash
# nlm 설치
pip install notebooklm-mcp-cli

# 공용 계정 로그인
nlm login --profile shared

# GitHub CLI 설치 확인
gh --version
```

---

## Stage 1 — Supabase 스키마 & 기초 데이터 구조

**목표:** `categories`, `articles`, `settings` 테이블 생성 및 기본 설정

**Supabase SQL Editor에서 실행:**

```sql
-- categories 테이블
CREATE TABLE categories (
  id         text PRIMARY KEY,
  name       text NOT NULL,
  name_ko    text,
  sub        text,
  area_type  text,
  insight    text,
  created_at timestamptz DEFAULT now()
);

-- articles 테이블
CREATE TABLE articles (
  id             text PRIMARY KEY,
  category_id    text REFERENCES categories(id),
  company        text,
  short          text,
  color_bg       text,
  color_text     text,
  kpi_value      text,
  kpi_label      text,
  title          text,
  description    text,
  body           text,
  metrics        jsonb DEFAULT '[]',
  tags           text[] DEFAULT '{}',
  source         text,
  url            text UNIQUE,
  published_date date,
  added_date     date DEFAULT CURRENT_DATE,
  verified       boolean DEFAULT false
);

-- settings 테이블 (공용 설정값 저장)
CREATE TABLE settings (
  key        text PRIMARY KEY,
  value      text NOT NULL,
  updated_at timestamptz DEFAULT now()
);

-- RLS: anon 읽기 허용
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles   ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read" ON categories FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON articles   FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON settings   FOR SELECT TO anon USING (true);
```

**프롬프트 (Claude Code):**
```
.env 파일을 읽어서 Supabase에 다음 9개 카테고리를 INSERT해줘.

카테고리 구조 (4개 영역):
1. Living Space Transformation (생활 공간 변화)
   - 1-1: Autonomous Home (자율 운영 홈) - 집이 스스로 환경과 기기를 운영하는 공간 - area_type: living_space
   - 1-2: Wellness Home (웰니스 홈) - 집이 건강·회복·예방을 관리하는 공간 - area_type: living_space
   - 1-3: Energy Optimized Home (에너지 최적화 홈) - AI 에너지 최적화로 생활비를 줄이는 집 - area_type: living_space
2. Consumption Transformation (소비 행동 변화)
   - 2-1: Agentic Commerce (에이전틱 커머스) - AI가 탐색·비교·구매를 대행하는 소비 - area_type: consumption
   - 2-2: Service-as-Living (생활의 서비스화) - 제품 소유에서 생활 기능 서비스 이용으로 - area_type: consumption
3. Personal Operating Transformation (개인 생활 운영 변화)
   - 3-1: Personal AI Agent (개인 AI 에이전트) - 개인의 일정·정보·루틴을 조율하는 AI - area_type: personal_operating
   - 3-2: Hyper-Capability (초확장 역량) - AI로 업무·학습·창작 역량이 증폭되는 변화 - area_type: personal_operating
4. Relationship & Care Transformation (관계·돌봄 변화)
   - 4-1: AI Companion (AI 동반자) - AI가 정서적 대화와 생활 동반자 역할 - area_type: relationship_care
   - 4-2: Remote Senior & Pet Care (원격 시니어·펫 케어) - 시니어·펫 돌봄을 원격·예측형으로 - area_type: relationship_care
```

**확인:**
```bash
curl -s "${SUPABASE_URL}/rest/v1/categories?select=id,name&order=id" \
  -H "apikey: ${SUPABASE_SERVICE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}"
# → 9개 카테고리 출력
```

---

## Stage 2 — 공유 Supabase 클라이언트 (supabase.js)

**목표:** 모든 HTML 페이지가 공통으로 사용하는 Supabase 클라이언트 생성

**프롬프트:**
```
docs/supabase.js 파일을 만들어줘.

요구사항:
- SUPABASE_URL, SUPABASE_ANON_KEY 하드코딩 (브라우저 공개용)
- fetchDB() 함수: categories + articles를 병렬 fetch해서
  { meta, categories: {id: {name,sub,type,insight}}, cases: [...] } 형태로 반환
- categories 테이블: old ID가 있으면 신규 체계로 클라이언트 리매핑
  (2-3→2-2, 3-3→3-2, 4-2→4-1, 4-3→4-2)
- NEW_CATEGORIES 상수로 9개 카테고리 정의 (DB 미이전 대응 fallback)
- supabaseDelete(ids, serviceKey) 함수: service_role key로 articles DELETE
- Supabase URL: [프로젝트 URL]
- Anon key: [anon key]
```

---

## Stage 3 — 네비게이션 & 공통 CSS

**목표:** 모든 페이지에 공통 nav와 디자인 시스템 적용

**프롬프트:**
```
docs/nav.js 를 만들어줘. 이 파일은 모든 페이지 <body>에 삽입되는 공통 네비게이션이야.

메뉴 구성 (순서대로):
- 홈 (index.html)
- 리서치 맵 (dashboard.html)
- 아티클 (archive.html)
- 아티클 관리 (articles.html)
- Trinity Eye (trinity.html)
- 미래의 모습 (slide-generation.html)

현재 페이지를 active로 표시하고, 로고는 "Life After AI"로 표시해줘.
index.html은 자체 nav를 가지므로 nav.js를 포함하지 않아.
```

---

## Stage 4 — 카테고리 체계 HTML 전체 반영

**목표:** 기존 HTML 파일들의 카테고리 레이블·색상·필터를 새 9개 체계로 일괄 업데이트

**프롬프트:**
```
아래 4개 파일의 카테고리 관련 내용을 모두 새 체계로 업데이트해줘.

신규 카테고리 체계:
- 영역 1 (g1, teal): 생활 공간 변화 → 1-1 Autonomous Home, 1-2 Wellness Home, 1-3 Energy Optimized Home
- 영역 2 (g2, amber): 소비 행동 변화 → 2-1 Agentic Commerce, 2-2 Service-as-Living
- 영역 3 (g3, green): 개인 생활 운영 변화 → 3-1 Personal AI Agent, 3-2 Hyper-Capability
- 영역 4 (g4, coral): 관계·돌봄 변화 → 4-1 AI Companion, 4-2 Remote Senior & Pet Care

수정 대상:
1. docs/dashboard.html — GROUPS 객체, 페이지 부제("4개 영역 · 9개 카테고리")
2. docs/archive.html — GROUPS 객체
3. docs/articles.html — CAT_MAP, 카테고리 드롭다운, 필터 칩 레이블
4. docs/index.html — 카테고리 카드 4개(Area 1~4), buildCard()의 cat-badge 색상 클래스(g1~g4)

index.html의 buildCard()는 cat.type === 'top' 대신
'g' + (c.category.split('-')[0] || '1') 방식으로 색상 클래스를 부여해줘.
```

---

## Stage 5 — 배치 URL 업로드 UI

**목표:** articles.html의 "URL로 추가" 탭에 텍스트 파일 배치 업로드 기능 추가

**프롬프트:**
```
docs/articles.html의 "URL로 추가" 탭 안에 서브탭을 추가해줘.

구조:
- [단일 URL] 탭: 기존 URL 입력 + 명령어 생성 유지
- [배치 업로드] 탭: 새로 추가

배치 업로드 탭 기능:
1. .txt 파일 드래그&드롭 또는 클릭 업로드 (FileReader로 내용 로드)
2. textarea 직접 붙여넣기 (파일 업로드와 공유)
3. 파일 형식: 줄당 URL 또는 "카테고리,URL" (예: 1-1,https://...), # 주석 무시
4. 실시간 파싱 프리뷰: 처리 대상 N개 / 주석 건너뜀 / 형식 오류 카운트
5. 카테고리별 컬러 뱃지 + URL 목록 (최대 50개 표시)
6. 옵션: 요청 간격(초, 기본 2), 드라이런 토글
7. "명령어 생성" 버튼 → heredoc 포함 터미널 명령어 생성
   (cat > /tmp/laf_batch_날짜.txt << 'URLEOF' ... URLEOF && python scraper/batch_add.py ...)
8. 복사 버튼

Claude Code 터미널에서 ! 명령어로 실행한다는 안내 포함.
```

---

## Stage 6 — 미래의 모습 페이지 기본 구조

**목표:** 슬라이드 생성 전용 페이지 생성 및 네비게이션 연결

**프롬프트:**
```
docs/slide-generation.html 을 새로 만들어줘.

페이지 구성:
- 헤더: "AI 생활 변화 Visualization" / "고객의 생활 변화 시나리오를 시각화 합니다."
- 탭 2개: [슬라이드 생성] [슬라이드 목록]

[슬라이드 생성] 탭:
- 시나리오 textarea (전폭, min-height 90px, 최대 2000자, 실시간 카운터)
- 옵션: 카테고리 포커스(9개), 형식(발표자 슬라이드 기본), 길이(짧게 기본), 언어(한국어 기본)
- 맞춤 프롬프트 textarea (전폭, min-height 48px)
  기본값: "업로드된 소스 내용을 바탕으로, 슬라이드 전체를 흥미진진한 만화 형식으로 만들어줘.
  각 슬라이드는 개별 만화 컷처럼 레이아웃을 구성하고, 캐릭터들이 대화하는 듯한 형식과
  시각적 효과를 포함해줘. 청중이 영화를 보는 것처럼 느낄 수 있게 해줘."
- 비주얼 스타일 칩 5개 (클릭 시 프롬프트에 스타일 텍스트 추가, 재클릭 해제):
  1. 애니메이션: src/assets/1.png — "Makoto Shinkai style, cinematic lighting, dramatic clouds, hyper-detailed, vibrant colors, lens flare, emotional"
  2. 픽사: src/assets/2.png — "Create a 3D animated, Pixar-style presentation slide. Use high-quality 3D rendered, cute characters with expressive faces and bright, cinematic, vibrant colors. Include a cozy and detailed background, focused on emotional storytelling."
  3. 지브리: src/assets/3.png — "Generate a Studio Ghibli inspired, hand-drawn anime illustration style slide. Soft pastel colors, warm lighting, detailed nature background with a nostalgic and artistic feel. Focus on emotional, serene scenes."
  4. 웹툰: src/assets/4.png — "Create a modern 2D anime illustration, vibrant, cell-shaded style. Dynamic composition, dramatic, high-contrast lighting, bold lines, and expressive anime characters. Cyberpunk or modern urban background."
  5. 3D 캐릭터: src/assets/5.png — "Generate a humorous, 3D animated, caricatured style slide. Focus on exaggerated facial expressions, funny poses, bright colors, and low-poly, fun, minimalist, high-quality rendered backgrounds."
- 스타일 칩: width 100px, 이미지 100×68px (object-fit:cover), 라벨 아래 표시
- "슬라이드 생성" CTA 버튼 (비활성→시나리오 10자 이상 + PAT 로드 시 활성)
- 4단계 진행 상태 표시 (스피너 + 단계 도트)
- 예시 시나리오 칩 5개

[슬라이드 목록] 탭:
- 슬라이드 카드 그리드
- 빈 상태 안내
- NotebookLM 링크 + PDF 다운로드 버튼

패널 가로: width 66.67%, max-width 900px (960px 이하 100%)
nav.js 포함, supabase.js 포함
```

---

## Stage 7 — GitHub Actions 클라우드 슬라이드 생성

**목표:** 로컬 서버 없이 버튼 클릭만으로 NotebookLM 슬라이드를 클라우드에서 생성

### 7-1. 워크플로우 파일

**프롬프트:**
```
.github/workflows/generate_slide.yml 을 만들어줘.

트리거: workflow_dispatch
입력값: job_id(required), scenario(required), category, format(기본: presenter_slides),
        length(기본: short), lang(기본: ko), custom_prompt

실행 환경: ubuntu-latest, permissions: contents write

스텝 순서:
1. actions/checkout@v4
2. Python 3.11 설정
3. notebooklm-mcp-cli==0.6.9 + requests beautifulsoup4 lxml + playwright 설치
   playwright install chromium --with-deps
4. NLM 인증: printf로 NLM_COOKIES_JSON Secret을 /tmp/nlm_cookies.json에 쓰고
   nlm login --manual -f /tmp/nlm_cookies.json 실행 후 파일 삭제
5. nlm login --check 로 인증 검증
6. python scraper/generate_slide_ci.py 실행
   (환경변수: JOB_ID, SCENARIO, CATEGORY, SLIDE_FORMAT, SLIDE_LENGTH, LANG, CUSTOM_PROMPT)
7. git config + git add docs/slides/ docs/data/slides.json + commit + push
```

### 7-2. CI 생성 스크립트

**프롬프트:**
```
scraper/generate_slide_ci.py 를 만들어줘.

환경변수로 파라미터를 받아 nlm CLI subprocess로 슬라이드를 생성하는 스크립트야.

처리 흐름:
1. nlm notebook create "LAF Slide: {시나리오 앞 48자}"
   → 출력에서 UUID 파싱
2. nlm source add {nb_id} --text {리서치DB텍스트} --title "Life After AI Research DB" --wait
   (docs/data/cases.json에서 카테고리 필터링해서 구성, 최대 60000자)
3. nlm source add {nb_id} --text {시나리오+스타일지침} --title "슬라이드 시나리오 및 스타일" --wait
4. nlm slides create {nb_id} --focus {시나리오200자+프롬프트280자} --language {ko|en}
   --format {fmt} --length {length} --confirm (timeout=30초)
5. nlm status artifacts {nb_id} --json 으로 5초마다 폴링 (최대 6분)
   → COMPLETE/READY 상태 확인
6. nlm download slide-deck {nb_id} --output docs/slides/{job_id}.pdf --format pdf --no-progress
7. docs/data/slides.json 업데이트 (신규 메타데이터 맨 앞에 추가)

기본 맞춤 프롬프트: "업로드된 소스 내용을 바탕으로, 슬라이드 전체를 흥미진진한 만화 형식으로..."
CATEGORY_NAMES 딕셔너리로 카테고리명 한→영 변환
```

### 7-3. GitHub Secret 등록

```bash
# 공용 NLM 계정으로 로그인
nlm login --profile shared

# 해당 프로필의 쿠키를 Secret으로 등록
cat ~/.notebooklm-mcp-cli/profiles/shared/cookies.json \
  | gh secret set NLM_COOKIES_JSON --repo {owner}/{repo}

# 확인
gh secret list --repo {owner}/{repo} | grep NLM
```

### 7-4. HTML GitHub API 연동

**프롬프트:**
```
docs/slide-generation.html의 슬라이드 생성 JS를 GitHub Actions API 연동으로 교체해줘.

제거: 로컬 서버(localhost:8765) 관련 모든 코드
추가:
- REPO = 'owner/repo', WORKFLOW = 'generate_slide.yml'
- PAT는 Supabase settings 테이블에서 자동 로딩 (키: github_pat)
  → loadPat() 함수: 페이지 로드 시 SUPABASE_URL/rest/v1/settings?key=eq.github_pat 조회
  → 성공 시 버튼 활성화, 실패 시 힌트 메시지 표시
- startGenerate(): job_id 생성(Date.now().toString(36)) → GitHub workflow_dispatch API 호출
  → 4초 대기 → pollWorkflow() 시작
- pollWorkflow(): 6초마다 /actions/workflows/.../runs 조회
  → runId 찾기 → 상태(queued/in_progress/completed) → 단계 표시
  → 완료 시 archive 탭으로 이동
  → GitHub Actions 실행 로그 링크 표시
- loadArchive(): raw.githubusercontent.com에서 slides.json 즉시 로드
  → fallback: ./data/slides.json
- PDF 다운로드 링크: GitHub Pages URL (https://{owner}.github.io/{repo}/slides/{id}.pdf)

PAT 발급 안내: github.com/settings/tokens → Fine-grained
→ Repository: 특정 레포만, Permissions: Actions Read&Write
```

---

## Stage 8 — Supabase 공용 PAT 설정

**목표:** 공용 GitHub PAT를 Supabase에 저장해 모든 사용자가 설정 없이 사용

**Supabase SQL Editor:**
```sql
-- settings 테이블이 없으면 Stage 1에서 이미 생성됨
-- PAT 삽입 (이미 있으면 덮어쓰기)
INSERT INTO settings (key, value)
VALUES ('github_pat', '여기에_PAT_값_입력')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
```

**또는 REST API:**
```bash
export $(grep -v '^#' .env | xargs)
curl -X POST "${SUPABASE_URL}/rest/v1/settings" \
  -H "apikey: ${SUPABASE_SERVICE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
  -H "Content-Type: application/json" \
  -H "Prefer: resolution=merge-duplicates" \
  -d '{"key":"github_pat","value":"여기에_PAT_값_입력"}'
```

**PAT 갱신:**
```bash
curl -X PATCH "${SUPABASE_URL}/rest/v1/settings?key=eq.github_pat" \
  -H "apikey: ${SUPABASE_SERVICE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"value":"새_PAT_값"}'
```

---

## 최종 확인 체크리스트

```
[ ] GitHub Pages 활성화 (Settings → Pages → main/docs)
[ ] Actions Workflow permissions: Read and write
[ ] Supabase categories 9개 등록 확인
[ ] Supabase settings.github_pat 등록 확인
[ ] NLM_COOKIES_JSON GitHub Secret 등록 확인
[ ] docs/slides/ 디렉토리 존재 (.gitkeep)
[ ] docs/data/slides.json 존재 (빈 배열 [])
[ ] nav.js에 모든 메뉴 포함 확인
[ ] index.html nav에 '미래의 모습' 포함 (자체 nav이므로 별도)
```

---

## 아키텍처 요약

```
브라우저 (GitHub Pages)
  ├── supabase.js        공용 Supabase 클라이언트 (articles, categories, settings)
  ├── nav.js             공통 네비게이션
  ├── dashboard.html     카테고리별 아티클 리서치 맵
  ├── archive.html       아티클 피드
  ├── articles.html      아티클 관리 (URL 추가, 배치 업로드, 목록 관리)
  └── slide-generation.html
        ↓ GitHub API (PAT from Supabase settings)
        workflow_dispatch → generate_slide.yml
              ↓ nlm (NLM_COOKIES_JSON Secret)
              NotebookLM 노트북 생성 → 슬라이드 생성 → PDF 다운로드
              ↓ git commit & push
        docs/slides/{id}.pdf   (GitHub Pages로 서빙)
        docs/data/slides.json  (슬라이드 메타데이터)

Supabase DB
  ├── categories    9개 카테고리
  ├── articles      수집된 아티클
  └── settings      github_pat (공용 PAT)

GitHub Actions
  ├── daily_update.yml         매일 자동 스크래핑 (KST 10:00)
  ├── add_article.yml          단일 URL 추가
  ├── delete_articles.yml      아티클 삭제
  └── generate_slide.yml       슬라이드 생성 (NotebookLM)

scraper/
  ├── batch_add.py             배치 URL 처리 (CLI)
  ├── generate_slide_ci.py     CI용 슬라이드 생성
  └── slide_server.py          로컬 개발용 슬라이드 서버
```

---

## 주의사항

| 항목 | 내용 |
|---|---|
| NLM 쿠키 유효기간 | Google 세션 기준 수 주~수개월, 만료 시 `nlm login --profile shared` 후 재등록 |
| GitHub PAT 유효기간 | 발급 시 설정한 기간, 만료 전 Supabase에서 갱신 |
| NotebookLM 노트북 누적 | 슬라이드 생성마다 노트북 생성 → 주기적 정리 필요 |
| Supabase anon key | 브라우저 공개용이므로 민감 데이터 직접 저장 금지 (PAT는 actions:write 전용으로 제한) |
| GitHub Pages 배포 시간 | 슬라이드 생성 완료 후 PDF 접근까지 약 1~2분 소요 |
