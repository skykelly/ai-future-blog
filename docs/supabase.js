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

  // categories: array → object keyed by id (기존 코드 호환)
  const categories = {};
  for (const c of catsArr) {
    categories[c.id] = { name: c.name, sub: c.sub, type: c.area_type, insight: c.insight };
  }

  // articles: Supabase 필드명 → 기존 cases 필드명으로 매핑
  const cases = artsArr.map(a => ({
    id:             a.id,
    category:       a.category_id,
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
  }));

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
