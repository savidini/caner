# Comprehensive Caner Rewrite Plan

## Summary

Replace the Flask/Jinja/Bootstrap monolith with a public, SPA-first application while preserving Caner’s useful behavior and playful identity.

- Backend: Python 3.13, FastAPI, Pydantic 2, synchronous SQLAlchemy 2, psycopg 3, Alembic, PostgreSQL 16, HTTPX.
- Frontend: [React 19.2](https://react.dev/versions), strict TypeScript, [Vite 8](https://vite.dev/blog/announcing-vite8), [React Router 8 Declarative Mode](https://reactrouter.com/start/modes), TanStack Query 5, shadcn/ui, [Tailwind CSS 4.3](https://tailwindcss.com/blog/tailwindcss-v4-3), React Hook Form, Zod, and Lucide.
- Toolchain: Node 22.22+, pnpm 10, Vitest, Testing Library, Playwright, Ruff, pytest.
- Deployment: separate Nginx web image and Python API image; the Python image also runs a dedicated worker. Docker Compose contains `postgres`, one-shot `migrate`, `api`, singleton `worker`, and `web`.
- Preserve menus, translations, prices, images, Caner/Rkr/MPS scores, votes, comments, recommendations, German/English, expert mode, price modes, and light/dark themes.
- Remove the page-view counter and public MPS-generation endpoint. Reset historical votes/comments/page views while preserving menu-derived data, scores, translations, and image cache.
- Deliver as an atomic production cutover after all parity, migration, accessibility, and browser tests pass.

## Implementation Changes

### 1. Repository and contract foundation

- Reorganize into `backend/`, `frontend/`, and deployment configuration, with feature-oriented modules and explicit imports; avoid generic repository layers and barrel-export trees.
- Replace import-time initialization with a FastAPI application factory, dependency-injected sessions/integration clients, and lifespan limited to resource setup—no feed downloads or AI work during API startup.
- Make FastAPI’s OpenAPI 3.1 document the sole API contract. Export it without running a server, generate committed TypeScript definitions with `openapi-typescript`, and build `openapi-fetch` plus `openapi-react-query` clients from them. CI regenerates and fails on drift. Generated files are never edited manually. This follows the supported [FastAPI SDK workflow](https://fastapi.tiangolo.com/advanced/generate-clients/) and [openapi-fetch contract model](https://openapi-ts.dev/openapi-fetch/).
- Enable `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `useUnknownInCatchVariables`. API payloads must use generated types; Zod is limited to runtime form UX while backend validation remains canonical.
- Preserve existing scoring formulas exactly with characterization tests: Niedersachsen `q` student-price cap at €2.50, Caner kcal/effective-price sorting, RkrN protein/price, current RkrR keyword penalties, and persisted MPS values.

### 2. Database, ingestion, and worker

- Introduce additive Alembic migrations so the old image remains rollback-capable:
  - Add stable canteen records with slugs, localized labels, source names, emoji, display order, and enabled state.
  - Extend existing meal/occurrence/cache tables with decimal price fields, parsed kcal/protein, marking-code arrays, stable canteen references, active flags, typed image-cache dates, and timestamps.
  - Add uniqueness for active `(meal, canteen, served_on)` occurrences after deterministic duplicate cleanup.
  - Add refresh-run metadata and new empty social tables for votes/comments plus recommendation-usage quotas.
  - Retain legacy social/page-view columns and tables through the rollback window; remove them only in a later cleanup release.
- Preserve meal IDs, German/English descriptions, MPS scores, occurrences, source metadata, image lookup records, and the image-cache volume. Do not copy old votes, comments, or page-view totals into the new tables.
- Make PostgreSQL—not process memory—the menu source of truth. A validated feed import runs transactionally, upserts changed prices/nutrition/markings, activates seen occurrences, and deactivates missing entries only within the successfully validated feed scope. Failed or suspiciously empty imports leave the last known good menu untouched.
- Store prices as exact decimal amounts and expose money as `{ amount: "2.50", currency: "EUR" }`; format them with `Intl.NumberFormat` in the browser.
- Run a dedicated singleton worker, guarded by PostgreSQL advisory locks:
  - Refresh immediately on worker startup, every six hours, and every ten minutes from 11:00–14:00 Europe/Berlin.
  - After successful imports, process missing meal translations and MPS values.
  - Persist comments immediately, then translate them asynchronously with retry/backoff; show the original text until translation succeeds.
  - Claim enrichment work with database status fields and `FOR UPDATE SKIP LOCKED`, requiring no Redis/Celery.
- Keep recommendations request-driven, but have the server derive the meal list from canteen/date rather than trusting client-supplied meals. Use structured prompts, a 45-second total timeout, cancellation, and safe Markdown output with no raw HTML.
- Configure canteen scope through a TOML file overridable by `CANTEENS_CONFIG_PATH`; default to Mensa Garbsen, Hauptmensa, and Contine.

### 3. Frontend and product experience

- Use one React Router application route with URL-backed state:
  - `lang=de|en`
  - ISO `date=YYYY-MM-DD`
  - stable `canteen=<slug>`
  - `expert=true`
  - `price=student|employee|guest`
- Accept legacy `mensa` names and `DD.MM.YYYY` dates once, then replace the URL with the canonical form. Date/canteen changes push browser history; display-only normalization uses replace.
- Build a refined Caner design system with CSS-first Tailwind tokens. Preserve the red/yellow identity, Caner portraits, recommendation personas, humor, and dark theme while meeting contrast and responsive-layout requirements.
- Centralize reusable components: app shell, page header, menu toolbar, meal table/card, price selector, Caner/score badges, dietary badges, vote controls, freshness banner, empty/error states, comments dialog, image dialog, and recommendation dialog.
- Render a semantic desktop table with caption/header scopes and a mobile list of meal articles. Provide real buttons, links, labels, headings, landmarks, skip link, dialog focus management, live mutation status, visible focus, reduced-motion handling, and at least 44×44 preferred touch targets. Treat the Website Specification’s [required accessibility items](https://specification.website/spec/accessibility/) as acceptance criteria.
- Keep role-and-name selectors as the browser automation interface. `data-testid` is allowed only where no semantic locator exists.
- Use TanStack Query for all server state:
  - Config cache: one hour.
  - Menu cache: five minutes with focus refetch and stale-data presentation.
  - Cursor-based comments as an infinite query.
  - Optimistic vote updates with rollback and invalidation.
  - Image queries triggered when meal media enters the viewport; successful immutable assets cache indefinitely and negative lookups respect the six-hour backend TTL.
- Store German/English interface messages in typed frontend modules with parity checks. API errors expose stable codes; the frontend localizes them.
- Render recommendation Markdown through a no-raw-HTML renderer. User comments and names always render as text.
- Keep the web manifest, robots.txt, sitemap, canonical metadata, language alternates, `llms.txt`, and `llms-full.txt`. Live menu content requires JavaScript by design; include a useful `<noscript>` explanation and machine-readable API link.
- Do not add accounts, administration, moderation UI, analytics vendors, SSR, Next.js, or a service worker in this rewrite.

## Public API and Security Contract

All application JSON endpoints use `/api/v1`; current `/api/*` endpoints are removed at cutover.

- `GET /api/v1/config`: enabled canteens, supported locales, price audiences, recommendation personas, form limits, and feature flags.
- `GET /api/v1/menus?canteen=&date=`: resolved selection, available/previous/next dates, freshness state, and meals containing localized names, categories, markings, structured nutrition, sustainability data, prices, scores, social totals/viewer vote, and cached image state. Missing parameters resolve to the configured default canteen and today or the next available date.
- `PUT /api/v1/meals/{meal_id}/vote`: idempotent `up|down`; one vote per signed actor, meal, and Europe/Berlin day, with switching allowed but no removal.
- `GET /api/v1/meals/{meal_id}/comments?locale=&cursor=&limit=` and `POST /api/v1/meals/{meal_id}/comments`: cursor pagination; `good|bad` rating, optional 80-character name, optional 1,000-character text, source locale, translation status, and localized fallback.
- `GET /api/v1/meals/{meal_id}/image?canteen=&date=` and `GET /api/v1/studifutter/assets/{file_id}?variant=thumb|full`: occurrence validation, lazy lookup, filesystem cache, immutable asset responses.
- `POST /api/v1/recommendations`: canteen, date, predefined persona or an optional 80-character custom persona; returns safe Markdown and never accepts arbitrary meal lists.
- `GET /health/live` and `GET /health/ready`; readiness checks PostgreSQL but not optional external providers.
- Root metadata endpoints remain available through Nginx proxying.

Use one error envelope: `{ error: { code, message, field_errors, request_id, retry_after_seconds } }`. Normalize validation failures into it and use correct 400/404/409/422/429/502/503 responses.

- Issue a signed, one-year, HttpOnly, Secure, SameSite=Lax `__Host-caner_actor` cookie in production, with a non-`__Host` development equivalent.
- Same-origin only; do not enable cross-origin API access.
- Apply Nginx per-IP limits and database-backed actor quotas. Defaults: 30 votes/minute per IP, 5 comments/10 minutes and 20/day per actor, 5 recommendations/hour and 20/day per actor, and 30 uncached image lookups/minute. Return `429` with `Retry-After`.
- Bundle all scripts, styles, icons, and fonts locally. Remove runtime CDNs and inline/eval scripts. Set CSP, `nosniff`, clickjacking, referrer, permissions, trusted-host, and cookie headers; terminate HTTPS/HSTS at the production edge.
- Cache fingerprinted assets for one year with `immutable`, revalidate SPA HTML, compress text responses, and retain immutable image-cache headers.
- Never return provider error bodies, secrets, raw exception messages, or AI-generated HTML to browsers.

## Verification, Delivery, and Cutover

- Preserve and relocate the 46 currently passing tests, then add:
  - Formula, parser, malformed-feed recovery, canteen configuration, transactional refresh, reconciliation, stale-data, enrichment retry, and image-cache tests.
  - FastAPI tests for every success/error response, OpenAPI operation ID, cookie behavior, quotas, prompt isolation, safe output, and external-provider timeout/auth failure.
  - PostgreSQL migration tests starting from a representative legacy schema/data dump, verifying retained core IDs/values, empty new social tables, duplicate cleanup, and old-image-readable legacy fields.
  - Frontend unit/component tests for URL parsing, localization parity, price/expert modes, score rendering, forms, optimistic updates, and loading/empty/stale/error states.
  - Playwright coverage in Chromium, Firefox, and WebKit for German/English, desktop/mobile, keyboard-only use, deep links and back/forward navigation, canteen/date changes, voting, comments, images, recommendations, dialog focus/escape, dark mode, and provider failures.
  - Automated axe checks with no serious/critical findings; critical workflows must use role-and-name locators.
  - Production-image smoke tests for headers, compression, immutable caching, SPA fallback, metadata endpoints, readiness, and absence of CDN requests.
- Add a 250 KB gzip initial-JavaScript budget and Lighthouse checks targeting LCP ≤2.5s and CLS ≤0.1, aligned with the [Core Web Vitals contract](https://specification.website/spec/performance/core-web-vitals/).
- Update CI to run backend lint/tests, frontend lint/typecheck/unit tests, OpenAPI drift, production Docker builds, Compose integration tests, and Playwright before publishing and signing both images.
- Update `AGENTS.md` with Docker-first commands, API regeneration, generated-file rules, reusable UI components, and the Python-source-of-truth rule. Replace djLint after Jinja removal with frontend lint/typecheck while retaining Ruff.
- Cut over atomically:
  1. Back up PostgreSQL and the meal-image volume.
  2. Pull both signed images and run the additive Alembic migration.
  3. Start API and worker, require readiness, then start web.
  4. Run production smoke workflows and confirm a successful refresh/enrichment cycle.
  5. Roll back by restoring the previous images if gates fail; additive legacy-compatible schema makes database downgrade unnecessary.
  6. Remove Flask/Jinja/Bootstrap, legacy API code, old social/page-view tables, supervisor/cron, and rollback-only columns only in a later cleanup release.

## Assumptions and Defaults

- Primary audience remains LUH students and staff, with mobile use prioritized.
- Browsers are current evergreen Chrome, Firefox, and Safari; Internet Explorer and JavaScript-disabled live menus are out of scope.
- PostgreSQL 16, Python 3.13, Europe/Berlin business dates, OpenRouter, Studentenwerk XML, and StudiFutter remain the operational dependencies.
- Existing formula behavior, recommendation personas, anonymous daily-vote semantics, and German/English content are contractual unless separately redesigned.
- The API may break cleanly because no legacy API compatibility window was requested; public legacy URLs receive client-side normalization.
- No destructive database cleanup occurs until the rewritten production release has passed its rollback window.
