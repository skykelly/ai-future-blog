/* supabase.js — Life After AI shared Supabase client
   - Public reads : anon key (hardcoded, safe for browser)
   - Delete writes: service_role key (stored in localStorage) */

const SUPABASE_URL      = 'https://ectgoceuuunftwuqnixq.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_wGqB5Ebkl_ytSIhj0Wvk6A_c6XEluEC';
const SB_KEY_STORE      = 'supabase_key';   // localStorage key

function getServiceKey() {
  return localStorage.getItem(SB_KEY_STORE) || '';
}

const _anonH = () => ({
  'apikey':        SUPABASE_ANON_KEY,
  'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
});

const _svcH = key => ({
  'apikey':        key,
  'Authorization': `Bearer ${key}`,
  'Content-Type':  'application/json',
  'Prefer':        'return=minimal',
});

/* ── 새 카테고리 체계 (4개 영역 · 9개) ─────────────────────────────────── */
const NEW_CATEGORIES = {
  '1-1': { name: 'Autonomous Home',          name_ko: '자율 운영 홈',       sub: '집이 스스로 환경과 기기를 운영하는 공간',    type: 'space' },
  '1-2': { name: 'Wellness Home',            name_ko: '웰니스 홈',          sub: '집이 건강·회복·예방을 관리하는 공간',      type: 'space' },
  '1-3': { name: 'Energy Optimized Home',    name_ko: '에너지 최적화 홈',   sub: 'AI 에너지 최적화로 생활비를 줄이는 집',    type: 'space' },
  '2-1': { name: 'Agentic Commerce',         name_ko: '에이전틱 커머스',    sub: 'AI가 탐색·비교·구매를 대행하는 소비',     type: 'commerce' },
  '2-2': { name: 'Service-as-Living',        name_ko: '생활의 서비스화',    sub: '제품 소유에서 생활 기능 서비스 이용으로',   type: 'commerce' },
  '3-1': { name: 'Personal AI Agent',        name_ko: '개인 AI 에이전트',   sub: '개인의 일정·정보·루틴을 조율하는 AI',     type: 'personal' },
  '3-2': { name: 'Hyper-Capability',         name_ko: '초확장 역량',        sub: 'AI로 업무·학습·창작 역량이 증폭되는 변화', type: 'personal' },
  '4-1': { name: 'AI Companion',             name_ko: 'AI 동반자',          sub: 'AI가 정서적 대화와 생활 동반자 역할',     type: 'care' },
  '4-2': { name: 'Remote Senior & Pet Care', name_ko: '원격 시니어·펫 케어',sub: '시니어·펫 돌봄을 원격·예측형으로',       type: 'care' },
};

/* 구 카테고리 → 신 카테고리 ID 매핑 (DB 미이전 상태 대응) */
const CAT_ID_REMAP = { '2-3':'2-2', '3-3':'3-2', '4-2':'4-1', '4-3':'4-2' };

/* ── fetchDB: returns data in the same shape as cases.json ─────────────── */
async function fetchDB() {
  const [catsRes, artsRes] = await Promise.all([
    fetch(`${SUPABASE_URL}/rest/v1/categories?select=*&order=id`,
          { headers: _anonH() }),
    fetch(`${SUPABASE_URL}/rest/v1/articles?select=*&order=published_date.desc,added_date.desc`,
          { headers: _anonH() }),
  ]);

  if (!catsRes.ok) throw new Error(`categories 로드 실패 (${catsRes.status})`);
  if (!artsRes.ok) throw new Error(`articles 로드 실패 (${artsRes.status})`);

  const catsArr = await catsRes.json();
  const artsArr = await artsRes.json();

  // Supabase categories를 새 체계로 병합 (DB 미이전 시 NEW_CATEGORIES로 대체)
  const dbCats = {};
  for (const c of catsArr) {
    dbCats[c.id] = { name: c.name, sub: c.sub, type: c.area_type, insight: c.insight };
  }
  const hasOldIds = Object.keys(dbCats).some(id => ['2-3','3-3','4-3'].includes(id));
  const categories = hasOldIds
    ? { ...NEW_CATEGORIES }
    : { ...NEW_CATEGORIES, ...dbCats };

  // articles: Supabase 필드명 → 기존 cases 필드명으로 매핑 + 구 category_id 리매핑
  const cases = artsArr.map(a => {
    const rawCat = a.category_id || '';
    const category = CAT_ID_REMAP[rawCat] || rawCat;
    return {
      id:             a.id,
      category,
      company:        a.company,
      short:          a.short,
      color_bg:       a.color_bg,
      color_text:     a.color_text,
      kpi_value:      a.kpi_value,
      kpi_label:      a.kpi_label,
      title:          a.title,
      description:    a.description,
      body:           a.body,
      metrics:        a.metrics        || [],
      tags:           a.tags           || [],
      source:         a.source,
      url:            a.url,
      published_date: a.published_date,
      added_date:     a.added_date,
      verified:       a.verified,
    };
  });

  const lastUpdated = artsArr[0]?.added_date
    ? new Date(artsArr[0].added_date).toISOString()
    : new Date().toISOString();

  return {
    meta: { total_cases: cases.length, last_updated: lastUpdated, version: '2.0' },
    categories,
    cases,
  };
}

/* ── supabaseDelete: DELETE articles by ID list ─────────────────────────── */
async function supabaseDelete(ids, serviceKey) {
  if (!ids || !ids.length) return true;

  const filter = ids.length === 1
    ? `id=eq.${ids[0]}`
    : `id=in.(${ids.map(id => `"${id}"`).join(',')})`;

  const resp = await fetch(
    `${SUPABASE_URL}/rest/v1/articles?${filter}`,
    { method: 'DELETE', headers: _svcH(serviceKey) }
  );
  return resp.ok || resp.status === 204;
}
