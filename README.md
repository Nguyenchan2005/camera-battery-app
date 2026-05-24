# Compact Camera Battery Database

This workspace contains a source-backed database for compact / fixed-lens digital
cameras and their battery systems.

Scope rules:

- Include compact, point-and-shoot, premium compact, travel zoom, waterproof
  compact, and bridge/superzoom cameras when the lens is fixed.
- Exclude DSLR, mirrorless interchangeable-lens, cinema camera, action camera,
  webcam, and smartphone products.
- Do not infer a battery from a similar model. If no source confirms the mapping,
  keep the camera in `data/camera_candidates.json` and
  `data/unresolved_models.json`; do not create a verified compatibility row.
- Every compatibility row must have a source URL, confidence, and verification
  date.

Files:

- `data/cameras.json` - camera records.
- `data/batteries.json` - battery records.
- `data/compatibility.json` - camera-to-battery mappings and sources.
- `data/camera_candidates.json` - source-backed camera existence records,
  including models whose battery is not verified yet.
- `data/sources.json` - source registry for batch imports.
- `data/unresolved_models.json` - confirmed camera candidates still needing
  manual battery verification.
- `schemas/*.schema.json` - machine-readable JSON schemas.
- `scripts/import_all_remaining.py` - source-backed master importer for
  non-Canon brands. It can be rerun and rolls back a single failed brand
  importer without damaging other data.
- `scripts/importers/common.py` - shared import, dedupe, source, and matching
  helpers used by brand importers.
- `scripts/importers/import_*.py` - brand importers. Importers without a
  source adapter report a warning instead of guessing battery mappings. Phase 2
  importers use Camera-wiki as a trusted candidate catalog when official
  archive-wide indexes are not machine-readable.
- `scripts/verify_unresolved_batteries.py` - Phase 3 verifier that promotes
  unresolved candidates only when an official/manual/trusted source explicitly
  confirms the battery or power source.
- `scripts/verifiers/verify_*.py` - brand-specific Phase 3 battery verifiers.
- `scripts/validate_and_export.py` - validates JSON, writes CSV, and builds the
  coverage reports.
- `exports/*.csv` - generated CSV output.
- `reports/coverage.md` - generated coverage report.
- `reports/coverage_by_series.md` - generated candidate coverage by series.
- `reports/coverage_by_brand.md` - generated candidate and source coverage by
  brand.
- `reports/unresolved_by_brand.md` - unresolved models grouped by brand.
- `reports/source_coverage_report.md` - source registry coverage.
- `reports/duplicate_alias_report.json` - generated duplicate alias check.
- `reports/duplicate_compatibility_report.json` - generated duplicate
  compatibility check.
- `reports/manual_audit_sample.md` - generated manual audit sample.
- `reports/unresolved_sample_by_brand.md` - generated unresolved sample by
  brand for manual verification planning.
- `reports/risky_short_model_matches.md` - generated short-model match risk
  report.
- `reports/phase3_verification_summary.md` - Phase 3 verifier run summary plus
  cumulative promotions from unresolved.
- `reports/verified_from_unresolved_by_brand.md` - cumulative Phase 3 verified
  promotions by brand.
- `reports/still_unresolved_by_brand.md` - unresolved models remaining by
  brand after Phase 3 verification.
- `reports/battery_source_quality_report.md` - source type and confidence
  coverage for Phase 3 battery mappings.
- `reports/http_status_report.md` - HTTP reachability warnings for checked
  verification URLs.

Run:

```powershell
py -3 scripts\import_all_remaining.py
py -3 scripts\verify_unresolved_batteries.py
py -3 scripts\validate_and_export.py
```

The current data is source-backed and has a broad candidate catalog, but battery
coverage is intentionally conservative. A camera stays unresolved until a source
explicitly confirms its battery or power source.

## Web App MVP

The React/Vite web app runs entirely in the browser and lazy-loads the JSON
database from `public/data/`. It does not call an AI API and does not infer battery
compatibility from nearby models or series.

Run:

```powershell
npm install
npm run dev
npm test
npm run build
npm run preview
npm run test:e2e
```

The main app entry points are:

- `src/lib/database.ts` - typed indexes, Fuse search, grouped compatibility,
  runtime validation, and template answer engine.
- `src/components/*` - search, result, source disclosure, and local inventory UI.
- `src/hooks/useLocalStorageIds.ts` - browser-local camera/battery inventory.
- `src/lib/database.test.ts` - database logic tests.

When the database changes, rerun the data scripts first, then rerun the app
checks:

```powershell
py -3 scripts\validate_and_export.py
npm test
npm run build
npm run test:e2e
```

Future AI integration should be added behind the `AnswerEngine` interface in
`src/lib/database.ts`. Only retrieved facts from the local database should be
sent to an AI layer, never the full database or unsourced guesses.

## Phase App 2 Notes

The app now lazy-loads the six JSON files from `public/data/*.json` at startup.
The original source database remains in `data/*.json`; copy updated JSON into
`public/data/` when refreshing the frontend dataset.

Phase App 2 adds:

- Loading and error states for database fetch failures.
- Database statistics and source-quality breakdown.
- Search result tabs for verified cameras, batteries, unresolved candidates,
  and all results.
- Match-reason labels and simple keyboard navigation in search results.
- Better camera and battery result panels, including grouped sources and
  inventory comparison.
- Unresolved manual-check copy flow.
- Inventory import/export JSON with id validation.
- Bulk paste inventory add: paste one camera or battery per line; the app only
  auto-adds unique exact matches and asks for manual choice on ambiguous lines.

When source JSON changes:

```powershell
py -3 scripts\validate_and_export.py
Copy-Item data\*.json public\data\ -Force
npm test
npm run build
```

## Phase App 3 Notes

Phase App 3 prepares the app for static deployment and offline lookup:

- `vite-plugin-pwa` generates `dist/sw.js` and `dist/manifest.webmanifest`.
- The service worker precaches the app shell and `public/data/*.json`, so lookup
  can keep working after the first successful online load.
- The UI shows network/cache state and a clear data-load error if a JSON file is
  missing or schema shape is wrong.
- `vercel.json` and `netlify.toml` are included for static deployment from
  `dist`.
- Playwright E2E tests run against `npm run preview`, not the dev server.

Deploy commands:

```powershell
npm install
npm run build
npm run preview
npm run test:e2e
```

Deploy settings:

- Vercel: framework `vite`, build command `npm run build`, output directory
  `dist`.
- Netlify: build command `npm run build`, publish directory `dist`.

If Playwright browsers are missing on a new machine:

```powershell
npx playwright install chromium
```

## Phase App 4 Notes

Phase App 4 adds optional Supabase Auth and cloud sync for the browser
inventory only. The camera/battery database is still static JSON loaded from
`public/data/*.json`; it is not copied to Supabase.

Supabase stores only one row per user:

- `user_id`
- `my_camera_ids`
- `my_battery_ids`
- `updated_at`

Create a Supabase project, then run this SQL in the Supabase SQL editor:

```sql
-- See supabase/schema.sql
create table user_inventory (
  user_id uuid primary key references auth.users(id) on delete cascade,
  my_camera_ids jsonb not null default '[]',
  my_battery_ids jsonb not null default '[]',
  updated_at timestamptz not null default now()
);

alter table user_inventory enable row level security;

create policy "Users can read own inventory"
on user_inventory
for select
using (auth.uid() = user_id);

create policy "Users can insert own inventory"
on user_inventory
for insert
with check (auth.uid() = user_id);

create policy "Users can update own inventory"
on user_inventory
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can delete own inventory"
on user_inventory
for delete
using (auth.uid() = user_id);
```

Local environment variables:

```powershell
Copy-Item .env.example .env.local
```

Then set:

```text
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

Do not use or expose a Supabase `service_role` key in the frontend.

Behavior:

- Without Supabase env vars or without login, the app stays local-only and uses
  `localStorage`.
- After login, the app loads cloud inventory, validates ids against the static
  local database, and never creates camera/battery records from cloud data.
- If cloud is empty, local inventory is uploaded.
- If local and cloud differ, the app asks whether to use local, use cloud, or
  merge.
- Local inventory updates immediately; cloud sync is debounced.
- If offline or sync fails, local data is preserved and can be retried later.

Deploy env:

- Vercel: add `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in Project
  Settings -> Environment Variables.
- Netlify: add the same variables in Site configuration -> Environment
  variables.
- GitHub Pages/static hosting: build with the env vars present, or omit them to
  run local-only. For a subpath deployment, set `VITE_BASE_PATH=/repo-name/`
  before `npm run build`.
