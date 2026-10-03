# Das Caner

Compact Flask app for LUH mensa menus. It imports the Studentenwerk Hannover XML feed, stores meals in PostgreSQL, ranks meals by calories per euro (`Cnr`), tracks votes, supports German/English UI text, and can use an OpenRouter-compatible chat model for MPS scores, meal-name translation, and recommendations.

## Quick Start

```bash
git clone https://github.com/match-Misc/caner.git
cd caner
cp .env.docker.example .env
docker compose up --build
```

Open `http://localhost:30823`.

## Development

Use Docker for app runs, checks, tests, and deployment verification.

```bash
docker compose build caner
docker compose run --rm --no-deps caner uvx ruff check .
docker compose run --rm --no-deps caner uvx djlint templates --profile=jinja --ignore=H021,H006,H030,H031
docker compose run --rm --no-deps caner uv run --with pytest python -m pytest
```

Run the app with `docker compose up`. The app creates required database tables on startup and refreshes menu data from the XML feed.

The **UI and performance checks** workflow builds the same Dockerfile, runs both
linters and the Python tests, then checks Chromium, Firefox and WebKit against a
disposable PostgreSQL database. Its `ui-review` artifact includes screenshots,
accessibility reports and traces for failures. The browser fixture uses synthetic
menus and mocked image/recommendation providers; it needs no production secrets.

The regression checks cover mobile/desktop and light/dark layouts, keyboard
controls, voting, comments, image loading, navigation and request failures. They
also enforce a fixed four-query budget for meal details and social totals across
1–30 meals, zero initial vote/comment API requests, and at most three concurrent
image lookups. Run `python -m tests.preview` only in an isolated Docker container
with a disposable database; it inserts fixture rows.

## Configuration

Copy `.env.docker.example` to `.env`. Required values:

- `SESSION_SECRET`
- `OPENROUTER_API_KEY`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

Useful optional values:

- `AI_MODEL`, `AI_MAX_TOKENS`: model and token limit for MPS and translation.
- `AI_MODEL_MAX`, `AI_MAX_TOKENS_MAX`: model and token limit for recommendations.
- `STARTUP_MPS_ENABLED`, `STARTUP_MPS_BACKGROUND`: calculate missing MPS scores after boot.
- `MEAL_TRANSLATION_ENABLED`, `STARTUP_TRANSLATIONS_ENABLED`, `STARTUP_TRANSLATIONS_BACKGROUND`: fetch missing English meal names.
- `MEAL_TRANSLATION_BATCH_SIZE`, `MEAL_TRANSLATION_WORKERS`: translation throughput.
- `MPS_REQUEST_DELAY_SECONDS`, `MEAL_TRANSLATION_REQUEST_DELAY_SECONDS`: OpenRouter pacing.
- `PROMPT_MPS`, `PROMPT_MEAL_TRANSLATION`, `PROMPT_COMMENT_TRANSLATION`: prompt overrides.
- `PROMPT_MARVIN`, `PROMPT_MARVIN_EN`, `PROMPT_GORDON`, `PROMPT_GORDON_EN`, `PROMPT_RICK`, `PROMPT_RICK_EN`, `PROMPT_TRUMP`: persona recommendation prompt overrides. Trump recommendations always use English.
- `PROMPT_RECOMMENDATION`, `PROMPT_RECOMMENDATION_EN`: fallback recommendation prompt overrides for custom recommenders.
- `SITE_URL`: public origin used for canonical URLs, sitemap links, and LLM discovery files.
- `LOG_DIR`: log directory, defaulting to `./logs` in local runs and `/app/logs` in the container.

Prompt override values must be single-line in `.env`; use `\n` for line breaks.

## Operations

Local deployment builds the image from the Dockerfile:

```bash
docker compose up --build -d
docker compose logs -f caner
```

Remote deployment pulls a prebuilt image:

```bash
CANER_IMAGE=ghcr.io/match-misc/caner:latest docker compose -f docker-compose.remote.yml pull
CANER_IMAGE=ghcr.io/match-misc/caner:latest docker compose -f docker-compose.remote.yml up -d
```

Postgres data is stored in `./data/postgres`. To reset local data:

```bash
docker compose down
sudo rm -rf ./data/postgres
docker compose up --build
```

## Stack

- Python 3.13, Flask, Gunicorn/gevent
- PostgreSQL, SQLAlchemy
- Bootstrap 5, Vanilla JS
- OpenRouter-compatible chat completions

## License

MIT
