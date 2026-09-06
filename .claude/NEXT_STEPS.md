# Stage 1 roadmap — item store (arXiv + lab blogs)

Goal: LLM-free pipeline that fetches arXiv papers + lab blog posts, normalizes them into
the canonical `items` schema (see `db/schema.sql`), and stores them in local Postgres.
No digest/synthesis yet — that's the next stage.

Working convention: manual/learning steps are marked **(you)**, boilerplate scaffolding
is marked **(me)**, and pieces where you drive with guidance are **(you, with help)**.
See CLAUDE.md for the full architecture context.

## Status

- [x] Repo scaffolded: `uv` project, `pyproject.toml`, deps installed (httpx, feedparser,
      psycopg[binary], python-dotenv)
- [x] `docker-compose.yml` for local Postgres written
- [x] `db/schema.sql` written (`items` table — see discussion in conversation history for
      the reasoning behind each column/index choice)
- [x] `.env` / `.env.example` set up
- [ ] Docker Desktop + WSL installed, machine reboot pending
- [ ] Postgres container running
- [ ] Schema applied to the database
- [ ] Config + DB connection layer
- [ ] arXiv fetcher
- [ ] Lab blog RSS fetcher
- [ ] Runner script

## Next step (pick up here after reboot)

**1. Start Postgres and apply the schema (you)**

```
docker compose up -d
docker compose ps
docker compose exec -T postgres psql -U ai_intel -d ai_intelligence < db/schema.sql
docker compose exec postgres psql -U ai_intel -d ai_intelligence -c "\d items"
```

Confirm `\d items` shows the expected columns, then report back before moving to step 2.

## Then

**2. Config + DB connection layer (me)** — `.env` loading, `psycopg` connection helper.
Boilerplate, will scaffold this directly.

**3. arXiv fetcher (you, with help)** — hit the arXiv API, parse the Atom response with
`feedparser`, map fields into the `items` schema. I'll give you the API query format and
field mapping; you write the fetch/parse code.

**4. Lab blog RSS fetcher (you, mostly solo)** — same shape as step 3, simpler (plain RSS,
no query params). Good second rep of the same pattern.

**5. Runner script (together)** — calls both fetchers, inserts into DB, prints a summary
(`N new items, M skipped as dupes`).

## Design decisions already made (see conversation for full reasoning)

- Python + `uv` for dependency/venv management (lockfile-based, like `package.json`)
- Local Postgres via Docker Compose for now (not hosted)
- `items` table dedupes on `UNIQUE (source_name, external_id)` — scoped per source, not
  globally, in case two sources produce colliding IDs
- `raw JSONB` column keeps the full original fetched payload as insurance while the schema
  is still evolving
- `source_type` will eventually include `news` alongside `lab_blog` and `paper` — not
  built yet, but the schema already accounts for it
- No ORM/migrations tool yet (plain SQL, one table) — revisit if schema churn increases
