-- ============================================================
-- Life After AI — Supabase Schema
-- ============================================================

-- ── categories ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
  id          TEXT PRIMARY KEY,          -- e.g. "1-1", "2-3"
  name        TEXT NOT NULL,             -- e.g. "AI Home"
  sub         TEXT,                      -- e.g. "집이 스스로 운영되는 공간"
  area_type   TEXT,                      -- e.g. "living_space"
  insight     TEXT,                      -- 카테고리 인사이트 문장
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── articles ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS articles (
  id             TEXT PRIMARY KEY,       -- e.g. "GOO-001"
  category_id    TEXT REFERENCES categories(id) ON DELETE SET NULL,
  company        TEXT NOT NULL,
  short          TEXT,                   -- 2~4자 약어
  color_bg       TEXT,
  color_text     TEXT,
  kpi_value      TEXT,
  kpi_label      TEXT,
  title          TEXT NOT NULL,
  description    TEXT,
  body           TEXT,
  metrics        JSONB    DEFAULT '[]',  -- [{value, label, trend}]
  tags           TEXT[]   DEFAULT '{}',
  source         TEXT,
  url            TEXT,
  published_date DATE,
  added_date     DATE,
  verified       BOOLEAN  DEFAULT FALSE,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS articles_category_id_idx ON articles(category_id);
CREATE INDEX IF NOT EXISTS articles_published_date_idx ON articles(published_date DESC);

-- ── Row Level Security ────────────────────────────────────────
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles   ENABLE ROW LEVEL SECURITY;

-- 누구나 읽기 가능 (public blog)
CREATE POLICY "Public read categories"
  ON categories FOR SELECT USING (true);

CREATE POLICY "Public read articles"
  ON articles FOR SELECT USING (true);
