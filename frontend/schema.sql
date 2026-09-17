CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  script_file TEXT NOT NULL,
  script TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  progress TEXT,
  run_id INTEGER,
  temp_url TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  done_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
