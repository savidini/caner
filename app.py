try:
    import gevent.monkey

    gevent.monkey.patch_ssl()
    gevent.monkey.patch_socket()
    print("Gevent monkey patching applied (ssl, socket).")
except ImportError:
    print("gevent not found, monkey patching skipped.")

import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import date, datetime
from urllib.parse import urlencode
from xml.sax.saxutils import escape as xml_escape

import markdown2
import requests
from dotenv import load_dotenv

from flask import (
    Flask,
    Response,
    jsonify,
    make_response,
    render_template,
    request,
    send_file,
)
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from comment_translation import choose_comment_text, translate_comment_text
from data_loader import load_parsed_mensa_data_to_db
from fetch_meal_translations import fetch_meal_translations
from i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    format_date_for_language,
    get_marking_info,
    get_meal_display_name,
    get_recommendation_prompt,
    get_translations,
    normalize_language,
    resolve_language,
    set_language_cookie,
    translate,
    translate_nutrient_label,
    translate_nutrient_value,
)
from menu_refresh import calculate_menu_refresh_delay_seconds
from meal_image_cache import (
    FULL_VARIANT,
    MealImageCacheError,
    MealImageCacheInvalidRequest,
    get_cached_studifutter_asset,
)
from meal_image_lookup_cache import find_or_cache_meal_image
from meal_translation import has_configured_translation_api_key
from mps_scoring import (
    MPSAuthenticationError,
    calculate_mps_for_meal,
    get_ai_max_tokens_max,
    get_ai_model_max,
    get_mps_request_delay_seconds,
    get_openrouter_base_url,
    has_configured_mps_api_key,
)
from models import Meal, MealComment, MealVote, PageView, db
from schema import ensure_application_schema
from studifutter import (
    StudiFutterError,
    is_directus_file_id,
)
from utils.xml_parser import (
    dedupe_marking_codes,
    get_available_dates,
    get_available_mensen,
    parse_mensa_data,
)

sys.setrecursionlimit(5000)


dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(
        f"Warning: .env file not found at {dotenv_path}. Ensure environment variables are set."
    )


# Utility function to convert markdown to HTML
def markdown_to_html(text):
    """Convert markdown text to inline HTML using the markdown2 library.

    This function converts markdown to HTML while ensuring the output
    is a single line without paragraph breaks, suitable for inline display.
    """
    if not text:
        return text

    # Normalize newlines: replace various newline types with spaces
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    # Convert markdown to HTML without break-on-newline to avoid unwanted <br> tags
    html = markdown2.markdown(text)

    # Remove block-level tags and replace with single spaces
    # This keeps inline formatting (bold, italic) but removes paragraph breaks
    html = re.sub(r"</?p\b[^>]*>", " ", html)  # Remove <p> and </p> tags
    html = re.sub(r"</?div\b[^>]*>", " ", html)  # Remove <div> tags
    html = re.sub(r"</?br\b[^>]*>", " ", html)  # Remove all <br> variants
    html = re.sub(r"</?h[1-6]\b[^>]*>", " ", html)  # Remove header tags

    # Collapse multiple whitespace characters to single spaces
    html = re.sub(r"\s+", " ", html).strip()

    return html


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_dir = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))
try:
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "app.log")
    file_handler = logging.FileHandler(log_file_path, mode="w")
except OSError:
    log_file_path = os.path.join(os.path.dirname(__file__), "app.log")
    file_handler = logging.FileHandler(log_file_path, mode="w")
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

for module_logger_name in (
    "data_loader",
    "fetch_meal_translations",
    "meal_translation",
    "mps_scoring",
    "utils.xml_parser",
):
    module_logger = logging.getLogger(module_logger_name)
    module_logger.setLevel(logging.INFO)
    module_logger.propagate = False
    if not module_logger.handlers:
        module_logger.addHandler(file_handler)
        module_logger.addHandler(console_handler)

logging.getLogger().setLevel(logging.INFO)

logger.info(f"Logging initialized. Log file at: {log_file_path}")


XML_SOURCE_URL = (
    "https://www.studentenwerk-hannover.de/fileadmin/user_upload/Speiseplan/SP-UTF8.xml"
)
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")
CLIENT_ID_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
_mensa_refresh_lock = threading.Lock()
_menu_refresh_thread = None


def get_site_origin():
    if SITE_URL:
        return SITE_URL
    return request.url_root.rstrip("/")


def absolute_site_url(path="/"):
    path = path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{get_site_origin()}{path}"


def build_index_path(language=DEFAULT_LANGUAGE, selected_date=None, selected_mensa=None):
    params = {"lang": normalize_language(language)}
    if selected_date:
        params["date"] = selected_date
    if selected_mensa:
        params["mensa"] = selected_mensa
    return f"/?{urlencode(params)}"


def build_index_url(language=DEFAULT_LANGUAGE, selected_date=None, selected_mensa=None):
    return absolute_site_url(
        build_index_path(
            language=language,
            selected_date=selected_date,
            selected_mensa=selected_mensa,
        )
    )


def set_client_id_cookie(response, client_id):
    response.set_cookie(
        "client_id",
        client_id,
        max_age=CLIENT_ID_COOKIE_MAX_AGE,
        httponly=True,
        secure=request.is_secure,
        samesite="Lax",
    )
    return response


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


STARTUP_MPS_ENABLED = env_flag("STARTUP_MPS_ENABLED", True)
STARTUP_MPS_BACKGROUND = env_flag("STARTUP_MPS_BACKGROUND", True)
MEAL_TRANSLATION_ENABLED = env_flag("MEAL_TRANSLATION_ENABLED", True)
STARTUP_TRANSLATIONS_ENABLED = env_flag("STARTUP_TRANSLATIONS_ENABLED", True)
STARTUP_TRANSLATIONS_BACKGROUND = env_flag("STARTUP_TRANSLATIONS_BACKGROUND", True)
MEAL_TRANSLATION_BATCH_SIZE = int(os.environ.get("MEAL_TRANSLATION_BATCH_SIZE", "20"))
MEAL_TRANSLATION_WORKERS = int(os.environ.get("MEAL_TRANSLATION_WORKERS", "2"))

# Reduced student price for Niedersachsen Menü (marking "q")
NIEDERSACHSEN_STUDENT_PRICE = "2,50"
COMMENT_TEXT_MAX_LENGTH = 1000
COMMENT_AUTHOR_MAX_LENGTH = 80
COMMENTS_DEFAULT_LIMIT = 5
COMMENTS_MAX_LIMIT = 25
MEAL_IMAGE_NEGATIVE_LOOKUP_TTL_SECONDS = int(
    os.environ.get("MEAL_IMAGE_NEGATIVE_LOOKUP_TTL_SECONDS", "21600")
)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Configure proxy support
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,  # Number of proxy servers in front of the app
    x_proto=1,  # Number of proxies handling protocol/SSL
    x_host=1,  # Number of proxies handling host headers
    x_prefix=1,  # Number of proxies handling path prefix
)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https://upload.wikimedia.org; "
        "font-src 'self' data: https://cdnjs.cloudflare.com; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'",
    )
    return response


# Configure the database from DATABASE_URL.
database_url = os.environ.get("DATABASE_URL")

if not database_url:
    logger.error(
        "Database configuration missing. Please ensure DATABASE_URL is set."
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_POOL_RECYCLE"] = 300  # Recycle connections every 5 minutes

# Initialize the database - moved db.init_app(app) inside app_context below


# --- START: Data Refresh Functions ---


def refresh_mensa_xml_data():
    global mensa_data, available_mensen, available_dates
    if not _mensa_refresh_lock.acquire(blocking=False):
        logger.warning("Skipping Mensa XML refresh because another refresh is active.")
        return False

    refresh_start = time.time()
    logger.info("Attempting to refresh Mensa XML data from %s", XML_SOURCE_URL)
    try:
        with app.app_context():
            logger.info("Refresh step 1/2: parsing Mensa XML once")
            current_mensa_data = parse_mensa_data(XML_SOURCE_URL)
            current_available_mensen = get_available_mensen(current_mensa_data)
            current_available_dates = get_available_dates(current_mensa_data)
            current_menu_items = sum(
                len(meals)
                for dates in current_mensa_data.values()
                for meals in dates.values()
            )

            if (
                current_mensa_data
                and current_available_mensen
                and current_available_dates
            ):
                logger.info("Refresh step 2/2: loading parsed Mensa XML into database")
                load_success = load_parsed_mensa_data_to_db(current_mensa_data)
                if load_success:
                    logger.info(
                        "Successfully loaded XML data into database during refresh."
                    )
                else:
                    logger.error(
                        "Failed to load XML data into database during refresh."
                    )

                mensa_data = current_mensa_data
                available_mensen = current_available_mensen
                available_dates = current_available_dates
                logger.info(
                    "Refreshed in-memory Mensa data: %s mensen, %s dates, %s menu items.",
                    len(available_mensen),
                    len(available_dates),
                    current_menu_items,
                )
                logger.info(
                    "Mensa XML refresh finished in %.2f seconds",
                    time.time() - refresh_start,
                )
                return load_success

            logger.warning(
                "Mensa XML parsing during refresh yielded no/incomplete data. In-memory data not updated."
            )
            logger.info(
                "Mensa XML refresh finished without in-memory update in %.2f seconds",
                time.time() - refresh_start,
            )
            return False
    except Exception as e:
        logger.error(f"Error during Mensa XML data refresh: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        _mensa_refresh_lock.release()


def batch_calculate_mps_scores():
    """Calculate MPS scores for meals that don't have them yet"""
    try:
        logger.info("Starting batch MPS calculation...")

        if not has_configured_mps_api_key():
            logger.warning(
                "Skipping batch MPS calculation because OPENROUTER_API_KEY is not configured."
            )
            return

        total_missing = Meal.query.filter(Meal.mps_score.is_(None)).count()
        logger.info(f"Found {total_missing} regular meals missing MPS scores")

        if total_missing == 0:
            logger.info("No meals missing MPS scores. Skipping calculation.")
            return

        total_processed = 0
        current_progress = 0
        auth_failed = False
        batch_start = time.time()

        meals_without_mps = Meal.query.filter(Meal.mps_score.is_(None)).all()
        logger.info(f"Processing {len(meals_without_mps)} regular meals...")

        for i, meal in enumerate(meals_without_mps, 1):
            # Double-check that this meal still doesn't have an MPS score
            # (in case it was calculated by another process or got updated)
            db.session.refresh(meal)
            if meal.mps_score is not None:
                logger.debug(f"Skipping meal {meal.id} - MPS score already exists")
                continue

            logger.info(
                f"Processing regular meal {i}/{len(meals_without_mps)} (total: {current_progress + 1}/{total_missing})"
            )
            try:
                mps_score = calculate_mps_for_meal(meal.description)
            except MPSAuthenticationError:
                auth_failed = True
                logger.error(
                    "Stopping batch MPS calculation because OpenRouter authentication failed. Check OPENROUTER_API_KEY."
                )
                break
            if mps_score is not None:
                meal.mps_score = mps_score
                total_processed += 1
                # Commit immediately after successful calculation
                try:
                    db.session.commit()
                    logger.info(
                        f"✓ Calculated and committed MPS {mps_score} for meal: {meal.description[:50]}..."
                    )
                except Exception as commit_error:
                    logger.error(
                        f"❌ Failed to commit MPS for meal {meal.id}: {commit_error}"
                    )
                    db.session.rollback()
                    continue
            else:
                logger.warning(
                    f"✗ Failed to calculate MPS for meal: {meal.description[:50]}..."
                )
            current_progress += 1
            # Add a small delay between API calls to avoid rate limiting
            request_delay_seconds = get_mps_request_delay_seconds()
            if request_delay_seconds > 0:
                time.sleep(request_delay_seconds)

        # All commits are done individually above
        if auth_failed:
            logger.warning("Batch MPS calculation stopped before completion.")
        else:
            logger.info("Batch MPS calculation completed successfully!")
        logger.info(
            "Summary: %s/%s meals processed and committed successfully in %.2f seconds",
            total_processed,
            total_missing,
            time.time() - batch_start,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in batch MPS calculation: {str(e)}")
        logger.error(traceback.format_exc())


def batch_fetch_meal_translations():
    """Fetch missing English meal translations without blocking page rendering."""
    if not MEAL_TRANSLATION_ENABLED:
        logger.info("Meal translation fetch disabled by MEAL_TRANSLATION_ENABLED.")
        return

    if not has_configured_translation_api_key():
        logger.warning(
            "Skipping meal translation fetch because OPENROUTER_API_KEY is not configured."
        )
        return

    try:
        result = fetch_meal_translations(
            overwrite_all=False,
            batch_size=MEAL_TRANSLATION_BATCH_SIZE,
            workers=MEAL_TRANSLATION_WORKERS,
        )
        if result == 0:
            logger.info("Missing meal translations fetched successfully.")
        else:
            logger.warning("Meal translation fetch finished with exit code %s.", result)
    except Exception as e:
        db.session.rollback()
        logger.error("Error in batch meal translation fetch: %s", e)
        logger.error(traceback.format_exc())


def perform_initial_app_loads():
    """Performs data loads required *directly* by the app at startup."""
    logger.info("Performing initial application data loads (Mensa XML)...")
    with app.app_context():
        refresh_mensa_xml_data()
    logger.info("Initial application data loads completed.")


def run_menu_refresh_scheduler():
    """Refresh visible menu data on a low-load schedule."""
    logger.info("Background Mensa menu refresh scheduler started.")
    while True:
        delay_seconds = calculate_menu_refresh_delay_seconds()
        logger.info(
            "Next scheduled Mensa XML refresh in %s seconds.",
            delay_seconds,
        )
        time.sleep(delay_seconds)

        scheduled_start = time.time()
        logger.info("Starting scheduled Mensa XML refresh.")
        refresh_success = refresh_mensa_xml_data()
        logger.info(
            "Scheduled Mensa XML refresh finished: success=%s duration=%.2fs",
            refresh_success,
            time.time() - scheduled_start,
        )


def start_menu_refresh_scheduler():
    global _menu_refresh_thread
    if _menu_refresh_thread and _menu_refresh_thread.is_alive():
        logger.info("Background Mensa menu refresh scheduler is already running.")
        return

    _menu_refresh_thread = threading.Thread(
        target=run_menu_refresh_scheduler,
        name="mensa-menu-refresh-scheduler",
        daemon=True,
    )
    _menu_refresh_thread.start()


def run_startup_mps_calculation():
    """Run startup MPS calculation with its own Flask app context."""
    logger.info("Background startup MPS worker started.")
    try:
        with app.app_context():
            batch_calculate_mps_scores()
    finally:
        logger.info("Background startup MPS worker finished.")


def run_startup_translation_fetch():
    """Run startup meal translation fetch with its own Flask app context."""
    logger.info("Background startup meal translation worker started.")
    try:
        with app.app_context():
            batch_fetch_meal_translations()
    finally:
        logger.info("Background startup meal translation worker finished.")


def start_mps_calculation_after_startup():
    if not STARTUP_MPS_ENABLED:
        logger.info("Startup MPS calculation disabled by STARTUP_MPS_ENABLED.")
        return

    if STARTUP_MPS_BACKGROUND:
        logger.info(
            "Starting MPS calculation in the background; the web app can serve pages while scores are calculated."
        )
        mps_thread = threading.Thread(
            target=run_startup_mps_calculation,
            name="startup-mps-calculation",
            daemon=True,
        )
        mps_thread.start()
        return

    logger.info(
        "Running MPS calculation synchronously during startup; first page load waits for this to finish."
    )
    batch_calculate_mps_scores()


def start_translation_fetch_after_startup():
    if not STARTUP_TRANSLATIONS_ENABLED:
        logger.info(
            "Startup meal translation fetch disabled by STARTUP_TRANSLATIONS_ENABLED."
        )
        return

    if not MEAL_TRANSLATION_ENABLED:
        logger.info("Meal translation fetch disabled by MEAL_TRANSLATION_ENABLED.")
        return

    if STARTUP_TRANSLATIONS_BACKGROUND:
        logger.info(
            "Starting meal translation fetch in the background; the web app can serve pages while translations are fetched."
        )
        translation_thread = threading.Thread(
            target=run_startup_translation_fetch,
            name="startup-meal-translation-fetch",
            daemon=True,
        )
        translation_thread.start()
        return

    logger.info(
        "Running meal translation fetch synchronously during startup; first page load waits for this to finish."
    )
    batch_fetch_meal_translations()


# --- END: Data Refresh Functions ---


def prepare_meal_for_display(meal_data, language):
    meal = dict(meal_data)
    try:
        db_meal = Meal.query.filter_by(description=meal["description"]).first()
        if db_meal:
            meal["id"] = db_meal.id
            meal["mps_score"] = db_meal.mps_score
            meal["description_en"] = db_meal.description_en
            meal["display_description"] = get_meal_display_name(db_meal, language)
            logger.debug(
                "Found DB meal %s for display: %s",
                db_meal.id,
                meal["description"][:50],
            )
        else:
            meal["id"] = 0
            meal["mps_score"] = None
            meal["description_en"] = None
            meal["display_description"] = meal["description"]
            logger.warning("Meal not found in database: %s", meal["description"][:50])
    except Exception as e:
        logger.error("Error looking up meal in database: %s", e)
        meal["id"] = 0
        meal["mps_score"] = None
        meal["description_en"] = None
        meal["display_description"] = meal.get("description", "")

    meal["price_student"] = get_effective_student_price(
        meal["price_student"], meal.get("marking", "")
    )
    return meal


def sort_meals_for_display(raw_meals, language):
    meals = [prepare_meal_for_display(meal, language) for meal in raw_meals]
    return sorted(
        meals,
        key=lambda meal: calculate_caner(
            extract_kcal(meal["nutritional_values"]), meal["price_student"]
        ),
        reverse=True,
    )


# Create tables and load data (Startup Sequence)
with app.app_context():  # Needed for db.create_all() and initial loads
    startup_start = time.time()
    logger.info("Application startup sequence started.")

    # Initialize the database within the app context
    db.init_app(app)
    logger.info("Startup step 1/6: SQLAlchemy initialized within app context.")

    # Initialize global data structures that will be populated by refresh functions
    mensa_data = {}  # Populated by refresh_mensa_xml_data
    available_mensen = []  # Populated by refresh_mensa_xml_data
    available_dates = []  # Populated by refresh_mensa_xml_data

    # Create database tables and perform initial data loads
    # No longer need a nested context here as db is initialized in the outer one
    logger.info("Startup step 2/6: creating database tables if needed.")
    db.create_all()
    logger.info("Database tables created (if not exist).")
    ensure_application_schema(db)
    logger.info("Application schema ensured.")

    # Perform initial loads needed *by the app* itself
    logger.info("Startup step 3/6: loading Mensa XML data.")
    perform_initial_app_loads()  # This now only loads Mensa XML

    logger.info("Startup step 4/6: starting lunch-window menu refresh scheduler.")
    start_menu_refresh_scheduler()

    # Calculate MPS scores for any meals that don't have them yet
    logger.info("Startup step 5/6: scheduling missing MPS score calculation.")
    start_mps_calculation_after_startup()
    logger.info("Startup step 6/6: scheduling missing meal translation fetch.")
    start_translation_fetch_after_startup()

    logger.info(
        "Application startup sequence finished in %.2f seconds.",
        time.time() - startup_start,
    )


@app.route("/")
def index():
    # Use the data loaded at startup
    global mensa_data, available_mensen, available_dates
    request_start = time.time()
    language = resolve_language(request)
    texts = get_translations(language)

    # Data is loaded at startup and refreshed by the lunch-window scheduler.

    # Increment the page view counter (with error handling)
    try:
        page_view = PageView.query.first()
        if page_view is None:
            # Create new PageView with default count=0, then increment it
            page_view = PageView()
            db.session.add(page_view)
            db.session.commit()  # Commit to get the ID
            page_view.count = 1
        else:
            page_view.count += 1
        db.session.commit()
    except Exception as e:
        logger.error(f"Error updating page view counter: {e}")
        db.session.rollback()  # Roll back in case of error

    selected_date = request.args.get("date")
    selected_mensa = request.args.get("mensa")
    expert_mode = request.args.get("expert") == "true"
    logger.info(
        "Rendering index: requested_date=%s requested_mensa=%s expert=%s lang=%s loaded_mensen=%s loaded_dates=%s",
        selected_date,
        selected_mensa,
        expert_mode,
        language,
        len(available_mensen),
        len(available_dates),
    )

    # Get today's date in the format used in the data
    today = datetime.now().strftime("%d.%m.%Y")
    today_dt = datetime.now()

    # Filter dates to only include -5 to +10 days from today
    filtered_dates = []
    for date_str in available_dates:
        try:
            date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            days_diff = (date_obj - today_dt).days
            if -5 <= days_diff <= 10:
                filtered_dates.append(date_str)
        except ValueError as e:
            logger.warning(f"Skipping unparsable date_str: {date_str} - {e}")
            pass

    # Sort the filtered dates
    filtered_dates.sort(key=lambda x: datetime.strptime(x, "%d.%m.%Y"))

    # Default to today's date if available. If not, try to find the next available date.
    if not selected_date:  # If no date was passed as a query parameter
        if today in filtered_dates:
            selected_date = today
        else:
            selected_date_candidate = None
            if filtered_dates:
                for date_str_in_loop in filtered_dates:
                    try:
                        current_list_date_obj = datetime.strptime(
                            date_str_in_loop, "%d.%m.%Y"
                        ).date()
                        if current_list_date_obj >= today_dt.date():
                            selected_date_candidate = date_str_in_loop
                            logger.info(
                                f"Found next available date (or today if it was parsed differently but matches): {selected_date_candidate}"
                            )
                            break  # Found the first suitable date
                    except ValueError:
                        logger.warning(
                            f"Invalid date format '{date_str_in_loop}' in filtered_dates during next day search."
                        )
                        continue

                # If no future/current date was found after checking all, use the first available date as a last resort.
                if not selected_date_candidate and filtered_dates:
                    selected_date_candidate = filtered_dates[0]
                    logger.info(
                        f"No future/current date found in filtered_dates. Defaulting to the first date in the list: {selected_date_candidate}"
                    )

                selected_date = selected_date_candidate
            else:
                logger.warning(
                    "No dates available in filtered_dates to select any default."
                )
                # Fallback to today's date if no date could be selected
                selected_date = today

    # Set default mensa to "Mensa Garbsen" if not selected
    if not selected_mensa:
        selected_mensa = "Mensa Garbsen"

    # Filter the available mensen to only include the required ones
    allowed_mensen = ["Mensa Garbsen", "Hauptmensa", "Contine"]
    filtered_mensen = [mensa for mensa in available_mensen if mensa in allowed_mensen]

    # Mapping for mensa emojis
    mensa_emojis = {
        "Mensa Garbsen": "🤖",
        "Contine": "🤑",
        "Hauptmensa": "👷",
    }

    # If mensa is specified, show only that one, otherwise show allowed mensen
    filtered_data = {}
    logger.info(
        "Index selection resolved: selected_date=%s selected_mensa=%s filtered_dates=%s filtered_mensen=%s",
        selected_date,
        selected_mensa,
        len(filtered_dates),
        filtered_mensen,
    )

    # Include the selected mensa first (even if it has no meals for the selected date)
    if selected_mensa in mensa_data and selected_date in mensa_data[selected_mensa]:
        filtered_data[selected_mensa] = sort_meals_for_display(
            mensa_data[selected_mensa][selected_date], language
        )
    elif selected_mensa:
        # Include the selected mensa with empty meals list so the UI can show
        # the "no meals available" message with navigation still functional
        filtered_data[selected_mensa] = []

    if not selected_date:
        selected_date = today

    # If no mensa is selected, include others from allowed list
    if not selected_mensa or selected_mensa == "":
        for mensa in allowed_mensen:
            if (
                mensa in mensa_data
                and selected_date in mensa_data[mensa]
                and mensa not in filtered_data
            ):
                filtered_data[mensa] = sort_meals_for_display(
                    mensa_data[mensa][selected_date], language
                )

    # Get the current page view count to display in the template
    current_page_views = 0
    try:
        page_view_obj = PageView.query.first()
        current_page_views = page_view_obj.count if page_view_obj else 0
    except Exception as e:
        logger.error(f"Error retrieving page view count: {e}")

    try:
        # Test JSON serialization before rendering
        # This will catch any potential circular references
        meal_counts = {
            mensa_name: len(meals) for mensa_name, meals in filtered_data.items()
        }
        logger.info(
            "Index prepared menu data: meal_counts=%s page_views=%s duration=%.2fs",
            meal_counts,
            current_page_views,
            time.time() - request_start,
        )
        json.dumps(
            {
                "data": filtered_data,
                "available_mensen": filtered_mensen,
                "available_dates": filtered_dates,
                "selected_date": selected_date,
                "selected_mensa": selected_mensa,
                "mensa_emojis": mensa_emojis,
                "page_views": current_page_views,
                "language": language,
            },
            default=str,
        )  # Use str as fallback for non-serializable objects

        response = make_response(
            render_template(
                "index.html",
                data=filtered_data,
                available_mensen=filtered_mensen,
                available_dates=filtered_dates,
                selected_date=selected_date,
                selected_mensa=selected_mensa,
                mensa_emojis=mensa_emojis,
                page_views=current_page_views,
                expert_mode=expert_mode,
                marking_info=get_marking_info(language),
                language=language,
                texts=texts,
                meta_description=texts["meta_description"],
                canonical_url=build_index_url(
                    language=language,
                    selected_date=selected_date,
                    selected_mensa=selected_mensa,
                ),
                alternate_urls={
                    supported_language: build_index_url(
                        language=supported_language,
                        selected_date=selected_date,
                        selected_mensa=selected_mensa,
                    )
                    for supported_language in sorted(SUPPORTED_LANGUAGES)
                },
                og_image_url=absolute_site_url("/static/img/caner.png"),
            )
        )
        set_language_cookie(response, language)
        return response
    except RecursionError as e:
        logger.error(f"RecursionError in index route: {e}")
        logger.error(f"Data that caused the error: {traceback.format_exc()}")
        return (
            "Entschuldigung, es gab einen Fehler bei der Verarbeitung der Daten. Bitte versuchen Sie es in ein paar Minuten erneut.",
            500,
        )
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        logger.error(traceback.format_exc())
        return (
            "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
            500,
        )


@app.route("/robots.txt")
def robots_txt():
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {absolute_site_url('/sitemap.xml')}",
            f"LLMs: {absolute_site_url('/llms.txt')}",
            "",
        ]
    )
    return Response(content, content_type="text/plain; charset=utf-8")


@app.route("/sitemap.xml")
def sitemap_xml():
    lastmod = date.today().isoformat()
    language_urls = {
        language: build_index_url(language=language)
        for language in sorted(SUPPORTED_LANGUAGES)
    }

    def url_entry(location, include_alternates=False):
        alternates = ""
        if include_alternates:
            alternates = "\n".join(
                "    "
                f'<xhtml:link rel="alternate" hreflang="{language}" '
                f'href="{xml_escape(url)}" />'
                for language, url in language_urls.items()
            )
        return "\n".join(
            [
                "  <url>",
                f"    <loc>{xml_escape(location)}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                alternates,
                "  </url>",
            ]
        )

    entries = [
        url_entry(absolute_site_url("/"), include_alternates=True),
        *[
            url_entry(location, include_alternates=True)
            for location in language_urls.values()
        ],
        url_entry(absolute_site_url("/llms.txt")),
        url_entry(absolute_site_url("/llms-full.txt")),
    ]
    xml = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
            *entries,
            "</urlset>",
            "",
        ]
    )
    return Response(xml, content_type="application/xml; charset=utf-8")


def build_llms_text(full=False):
    default_texts = get_translations(DEFAULT_LANGUAGE)
    lines = [
        "# Das Caner",
        "",
        f"> {default_texts['llms_summary']}",
        "",
        "## Primary Content",
        "",
        (
            f"- [{default_texts['llms_primary_content']}]"
            f"({build_index_url(DEFAULT_LANGUAGE)})"
        ),
        "",
        "## Machine-Readable Endpoints",
        "",
        f"- [Sitemap]({absolute_site_url('/sitemap.xml')})",
        f"- [Full LLM context]({absolute_site_url('/llms-full.txt')})",
        "",
        "## Notes",
        "",
        f"- {default_texts['llms_language_note']}",
        f"- {default_texts['llms_data_note']}",
    ]

    if full:
        lines.extend(["", "## Localised Summaries", ""])
        for language in sorted(SUPPORTED_LANGUAGES):
            texts = get_translations(language)
            lines.extend(
                [
                    f"### {language}",
                    "",
                    texts["llms_summary"],
                    "",
                    f"- {texts['llms_primary_content']}: {build_index_url(language)}",
                    f"- {texts['llms_language_note']}",
                    f"- {texts['llms_data_note']}",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


@app.route("/llms.txt")
def llms_txt():
    return Response(
        build_llms_text(full=False),
        content_type="text/plain; charset=utf-8",
    )


@app.route("/llms-full.txt")
def llms_full_txt():
    return Response(
        build_llms_text(full=True),
        content_type="text/plain; charset=utf-8",
    )


@app.route("/site.webmanifest")
def site_webmanifest():
    texts = get_translations(DEFAULT_LANGUAGE)
    manifest = {
        "name": texts["app_title"],
        "short_name": texts["app_short_name"],
        "description": texts["meta_description"],
        "start_url": build_index_path(DEFAULT_LANGUAGE),
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffcc00",
        "theme_color": "#ff3333",
        "icons": [
            {
                "src": "/static/img/caner.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            }
        ],
    }
    return Response(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        content_type="application/manifest+json; charset=utf-8",
    )


@app.template_filter("format_date")
def format_date(date_str, language=DEFAULT_LANGUAGE):
    try:
        return format_date_for_language(date_str, language)
    except Exception as e:
        logger.error(
            "An unexpected error occurred in format_date with %s: %s", date_str, e
        )
        return date_str


@app.template_filter("extract_kcal")
def extract_kcal(naehrwert_str):
    try:
        if not naehrwert_str:
            return 0
        # Example: Brennwert=3062 kJ (731 kcal), Fett=8,4g...
        if "kcal" in naehrwert_str:
            start = naehrwert_str.index("(") + 1
            end = naehrwert_str.index("kcal")
            return int(naehrwert_str[start:end].strip())
        return 0
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in extract_kcal with {naehrwert_str}: {e}"
        )
        return 0


def get_effective_student_price(price_student, marking):
    """Return the effective student price for a meal.

    If the meal is tagged as Niedersachsen Menü (marking code "q") and the
    original student price exceeds 2.50 €, the price is capped at
    NIEDERSACHSEN_STUDENT_PRICE so that scores are calculated correctly.

    :param price_student: str or None, student price in German format (e.g. "3,40")
    :param marking: str or None, comma-separated marking codes (e.g. "v,q,s")
    :returns: str or None, effective student price in German format
    """
    if not marking:
        return price_student
    markings = dedupe_marking_codes(marking).lower().replace(" ", "").split(",")
    if "q" in markings:
        if not price_student:
            return price_student
        try:
            price = float(price_student.replace(",", ".").strip())
            cap_price = float(
                str(NIEDERSACHSEN_STUDENT_PRICE).replace(",", ".").strip()
            )
            if price > cap_price:
                return NIEDERSACHSEN_STUDENT_PRICE
        except (ValueError, AttributeError):
            pass
    return price_student


@app.template_filter("calculate_caner")
def calculate_caner(kcal, price_student):
    # Input validation for price_student
    if (
        price_student is None
        or not isinstance(price_student, str)
        or price_student.strip() == ""
    ):
        logger.warning(
            f"Invalid price_student input in calculate_caner: Received '{price_student}' (type: {type(price_student)}). Treating as 0."
        )
        return 0

    try:
        # Attempt to convert price from string to float (replace comma with dot)
        price_str_cleaned = price_student.replace(",", ".").strip()
        price = float(price_str_cleaned)

        # Check for non-positive price after conversion
        if price <= 0:
            logger.warning(
                f"Non-positive price detected in calculate_caner: kcal={kcal}, price_student='{price_student}' resulted in price={price}. Treating as 0."
            )
            return 0

        # Ensure kcal is a number (it should be from extract_kcal)
        if not isinstance(kcal, (int, float)):
            logger.warning(
                f"Invalid kcal input in calculate_caner: Received '{kcal}' (type: {type(kcal)}). Cannot calculate Caner score."
            )
            return 0

        # Calculate and return Caner score
        return round(kcal / price, 2)

    except ValueError:
        # Log specific error if float conversion fails
        logger.warning(
            f"Could not convert price_student='{price_student}' to float in calculate_caner. Original kcal={kcal}. Treating as 0."
        )
        return 0
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"An unexpected error occurred in calculate_caner with kcal={kcal}, price_student='{price_student}': {e}"
        )
        logger.error(traceback.format_exc())  # Log stack trace for unexpected errors
        return 0


@app.template_filter("extract_protein")
def extract_protein(naehrwert_str):
    try:
        if not naehrwert_str:
            return 0.0
        # Example: Brennwert=3062 kJ (731 kcal), Eiweiß=25,7g, ...
        if "Eiweiß" in naehrwert_str:
            match = re.search(r"Eiweiß=([\d,]+)g", naehrwert_str)
            if match:
                return float(match.group(1).replace(",", "."))
        return 0.0
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in extract_protein with {naehrwert_str}: {e}"
        )
        return 0.0


@app.template_filter("calculate_rkr_nominal")
def calculate_rkr_nominal(protein_g, price_student):
    if (
        price_student is None
        or not isinstance(price_student, str)
        or price_student.strip() == ""
    ):
        logger.warning(
            f"Invalid price_student input in calculate_rkr_nominal: Received '{price_student}' (type: {type(price_student)}). Treating as 0."
        )
        return 0.0

    try:
        price_str_cleaned = price_student.replace(",", ".").strip()
        price = float(price_str_cleaned)

        if price <= 0:
            logger.warning(
                f"Non-positive price detected in calculate_rkr_nominal: protein_g={protein_g}, price_student='{price_student}' resulted in price={price}. Treating as 0."
            )
            return 0.0

        if not isinstance(protein_g, (int, float)):
            logger.warning(
                f"Invalid protein_g input in calculate_rkr_nominal: Received '{protein_g}' (type: {type(protein_g)}). Cannot calculate Rkr nominal."
            )
            return 0.0

        if protein_g == 0:  # Avoid division by zero if protein is 0
            return 0.0

        return round(protein_g / price, 2)

    except ValueError:
        logger.warning(
            f"Could not convert price_student='{price_student}' to float in calculate_rkr_nominal. Original protein_g={protein_g}. Treating as 0."
        )
        return 0.0
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in calculate_rkr_nominal with protein_g={protein_g}, price_student='{price_student}': {e}"
        )
        logger.error(traceback.format_exc())
        return 0.0


PENALTY_KEYWORDS = [
    # Vegetables
    "zucchini",
    "paprika",
    "karotten",
    "brokkoli",
    "blumenkohl",
    "spinat",
    "aubergine",
    "erbsen",
    "bohnen",
    "spargel",
    "lauch",
    "sellerie",
    "zwiebeln",
    "knoblauch",
    "schalotten",
    "salat",
    "rucola",
    "feldsalat",
    "eisbergsalat",
    # Mushrooms
    "champignons",
    "pfifferlinge",
    "steinpilze",
    "pilze",
    # Fruits
    "äpfel",
    "birnen",
    "quitten",
    "kirschen",
    "pflaumen",
    "aprikosen",
    "pfirsiche",
    "nektarinen",
    "erdbeeren",
    "himbeeren",
    "heidelbeeren",
    "brombeeren",
    "johannisbeeren",
    "orangen",
    "mandarinen",
    "zitronen",
    "limetten",
    "grapefruits",
    "bananen",
    "ananas",
    "mango",
    "kiwi",
    "melonen",
    "rosinen",
    "getrocknete pflaumen",
    "datteln",
    # Fish & Seafood
    "lachs",
    "thunfisch",
    "forelle",
    "kabeljau",
    "hering",
    "garnelen",
    "krabben",
    "muscheln",
    "austern",
    "tintenfisch",
    "hummer",
    # Hidden Vegetables/Fruits
    "gemüseaufläufe",
    "gratins mit gemüse",
    "pizza mit gemüse oder pilzen",
    "wraps mit salat",
    "sandwiches mit gemüse",
    "burger mit tomaten oder gurken",
    "soßen mit gemüsebasis",
    "tomatensoße",
    "ratatouille",
    "gemüsesuppe",
    "desserts mit obst",
    "apfelkuchen",
    "erdbeertorte",
    "obstsalat",
    # Plant-based Components
    "viel petersilie",
    "basilikum",
    "koriander",
    "dill",
    "soja-fleischalternativen",
    "gemüse-fleischalternativen",
    "gemüsesäfte",
    "smoothies",
    "karottensaft",
    "multivitaminsaft",
    "vegan",
    "cremige tomatensauce",
]


@app.template_filter("calculate_rkr_real")
def calculate_rkr_real(protein_g, price_student, meal_description):
    rkr_value = calculate_rkr_nominal(
        protein_g, price_student
    )  # This is already rounded to 2 decimal places

    if rkr_value == 0.0:  # If nominal is 0, no point in further processing
        return 0.0

    description_lower = ""
    # Ensure meal_description is a non-empty string before lowercasing
    if meal_description and isinstance(meal_description, str):
        description_lower = meal_description.lower()
    else:
        # If meal_description is None or not a string, or empty, no penalties can be applied
        return rkr_value

    # Special handling for "erbsen" and "cremige/cremiger tomatensauce" - multiply by -1 (make negative)
    if (
        "erbsen" in description_lower
        or "cremige tomatensauce" in description_lower
        or "cremiger tomatensauce" in description_lower
    ):
        rkr_value *= -1

    # Apply regular penalties for other keywords (excluding "erbsen" and "cremige/cremiger tomatensauce")
    for keyword in PENALTY_KEYWORDS:
        if (
            keyword not in ["erbsen", "cremige tomatensauce"]
            and keyword in description_lower
        ):
            rkr_value /= 2

    # The result of rkr_value / 2 operations might result in more than 2 decimal places
    # So we round again at the end.
    return round(rkr_value, 2)


@app.template_filter("generate_caner_symbols")
def generate_caner_symbols(caner_score):
    if caner_score <= 0:
        return ""

    # Format the caner value with 2 decimal places and comma as decimal separator
    caner_value_formatted = f"{caner_score:.2f} Cnr".replace(".", ",")

    # Calculate full icons (100s) and partial icon percentage
    full_icons = int(
        caner_score // 100
    )  # Remove the min(5, ...) to allow more than 5 icons
    remainder = caner_score % 100

    has_partial = remainder > 0
    partial_percentage = int(remainder)  # Percentage of the next 100

    # Generate HTML for the icons
    icons_html_parts = []

    # Add full icons
    for _ in range(full_icons):
        icons_html_parts.append(
            '<img src="/static/img/caner.png" class="caner-icon light-caner">'
            '<img src="/static/img/darkcaner.png" class="caner-icon dark-caner">'
        )

    # Add partial icon if needed
    if has_partial:
        # Calculate width based on percentage (18px is the icon width)
        width_px = (18 * partial_percentage) / 100

        # Create partial icon with cropped width
        icons_html_parts.append(
            f'<span class="caner-icon-partial" style="--crop-percentage: {width_px}px">'
            '<img src="/static/img/caner.png" class="light-caner">'
            '<img src="/static/img/darkcaner.png" class="dark-caner">'
            "</span>"
        )

    icons_html = "".join(icons_html_parts)
    return f'<span class="caner-value">{caner_value_formatted}</span><span class="caner-symbol">{icons_html}</span>'


@app.template_filter("get_dietary_info")
def get_dietary_info(marking, language=DEFAULT_LANGUAGE):
    """Extract dietary information from marking codes and show as emojis with tooltips"""
    if not marking:
        return ""

    markings = dedupe_marking_codes(marking).lower().replace(" ", "").split(",")
    localized_marking_info = get_marking_info(language)

    emoji_spans = []
    for code in markings:
        if code in localized_marking_info:
            title = localized_marking_info[code]["title"]
            emoji = localized_marking_info[code].get("emoji", "")
            dark_emoji = localized_marking_info[code].get("dark_emoji", "")
            span_content = ""
            if emoji:
                span_content += (
                    f'<span class="food-marking food-marking-light" '
                    f'title="{title}">{emoji}</span>'
                )
            if dark_emoji:
                span_content += (
                    f'<span class="food-marking food-marking-dark" '
                    f'title="{title}">{dark_emoji}</span>'
                )
            if "images" in localized_marking_info[code]:
                for img in localized_marking_info[code]["images"]:
                    span_content += (
                        f'<img class="food-marking-img food-marking-light" '
                        f'src="{img}" title="{title}" alt="{title}">'
                    )
            if "dark_images" in localized_marking_info[code]:
                for img in localized_marking_info[code]["dark_images"]:
                    span_content += (
                        f'<img class="food-marking-img food-marking-dark" '
                        f'src="{img}" title="{title}" alt="{title}">'
                    )
            if span_content:
                emoji_spans.append(span_content)

    return " ".join(emoji_spans)


@app.template_filter("format_nutritional_values")
def format_nutritional_values(value_str, language=DEFAULT_LANGUAGE):
    if not value_str or not isinstance(value_str, str):
        message = translate(language, "no_nutritional_values")
        return f"<p class='text-muted'><small>{message}</small></p>"

    # Regex to split by comma BUT not if the comma is followed by a digit and then a letter (e.g., "2,9g")
    # This aims to split between "key=value" pairs like "Eiweiß=25,7g, Salz=2,1g"
    # It splits on commas that are likely delimiters between nutrient entries.
    parts = re.split(r",\s*(?=[A-Za-zÀ-ÖØ-öø-ÿ]+[=])", value_str)

    if not parts or (len(parts) == 1 and "=" not in parts[0]):
        # If splitting didn't work or only one non-key-value part, return a formatted message
        # This might happen if the format is very different from expected.
        prefix = translate(language, "nutritional_values_prefix")
        return f"<p class='text-muted'><small>{prefix}: {value_str}</small></p>"

    html_output = "<ul class='list-unstyled mb-0 nutrient-list'>"
    for part in parts:
        part = part.strip()
        if "=" in part:
            key_value = part.split("=", 1)
            key = translate_nutrient_label(key_value[0].strip(), language)
            value = key_value[1].strip() if len(key_value) > 1 else ""
            value = translate_nutrient_value(value, language)

            # Special handling for Brennwert to put (kcal) in small tags
            # This should be applied before splitting for "davon", so it operates on the full value if Brennwert itself has sub-parts.
            if "Brennwert" in key and "kcal" in value:
                # Make the (xxx kcal) part smaller and wrap kJ if also present
                value = re.sub(r"\(([^)]+kcal[^)]*)\)", r"(<small>\1</small>)", value)

            # Handle "davon" constituents for the current nutrient value
            processed_value = value  # Default to original value (after brennwert modification if applicable)
            if ", davon " in value:  # Check in the potentially modified value
                value_components = value.split(", davon ", 1)
                # Ensure the "davon" part is not bold, and is on a new line.
                davon_label = "of which" if normalize_language(language) == "en" else "davon"
                processed_value = f"{value_components[0].strip()}<br>{davon_label} {value_components[1].strip()}"

            html_output += f"<li><strong>{key}:</strong> {processed_value}</li>"
        elif part:  # Only add if part is not empty after stripping
            # Fallback for parts not in key=value format (should be less common now)
            html_output += f"<li>{part}</li>"

    html_output += "</ul>"
    return html_output


# Get or create a client ID from cookie
def get_client_id():
    client_id = request.cookies.get("client_id")
    if not client_id:
        client_id = str(uuid.uuid4())
    return client_id


# Get meal vote counts for a specific meal
def get_vote_counts(meal_id):
    # Convert to integer if it's a string
    meal_id_int = int(meal_id) if isinstance(meal_id, str) else meal_id
    upvotes = MealVote.query.filter_by(meal_id=meal_id_int, vote_type="up").count()
    downvotes = MealVote.query.filter_by(meal_id=meal_id_int, vote_type="down").count()
    return {"up": upvotes, "down": downvotes}


def get_comment_count(meal_id):
    meal_id_int = int(meal_id) if isinstance(meal_id, str) else meal_id
    return MealComment.query.filter_by(meal_id=meal_id_int).count()


def serialize_comment(comment, language):
    display_text = choose_comment_text(comment, language)
    return {
        "id": comment.id,
        "meal_id": comment.meal_id,
        "rating": comment.rating,
        "author_name": comment.author_name or "",
        "text": display_text,
        "has_text": bool(display_text),
        "translation_failed": bool(comment.translation_failed),
        "created_at": comment.created_at.isoformat() if comment.created_at else "",
    }


# Check if a client has already voted for a meal today
def has_voted_today(meal_id, client_id):
    # Convert to integer if it's a string
    meal_id_int = int(meal_id) if isinstance(meal_id, str) else meal_id
    today = date.today()
    vote = MealVote.query.filter_by(
        meal_id=meal_id_int, client_id=client_id, date=today
    ).first()
    return vote is not None


# AP health check route
@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
    Pings the database to check connectivity.
    Does NOT count as a page view.
    """
    try:
        # Perform a simple query to check database connectivity
        db.session.execute(text("SELECT 1"))
        # If the query succeeds, the database is reachable
        return jsonify({"status": "UP", "database": "OK"}), 200
    except Exception as e:
        # If the query fails, the database is not reachable
        logger.error(f"Health check failed: Database connection error - {e}")
        logger.error(traceback.format_exc())
        return jsonify({"status": "DOWN", "database": "Error", "error": str(e)}), 500


# API route to handle meal votes
@app.route("/api/vote", methods=["POST"])
def vote():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    meal_id = data.get("meal_id")
    vote_type = data.get("vote_type")

    if not meal_id or vote_type not in ["up", "down"]:
        return jsonify({"error": "Invalid input"}), 400

    try:
        meal_id_int = int(meal_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid input"}), 400

    meal = db.session.get(Meal, meal_id_int)
    if not meal:
        return jsonify({"error": "Meal not found"}), 404

    # Get or set client ID from cookie
    client_id = get_client_id()
    today = date.today()

    # Check if client already voted for this meal today
    existing_vote = MealVote.query.filter_by(
        meal_id=meal_id_int, client_id=client_id, date=today
    ).first()

    if existing_vote:
        # If vote type is different, update it
        if existing_vote.vote_type != vote_type:
            existing_vote.vote_type = vote_type
            db.session.commit()
            message = "Vote updated"
        else:
            message = "Already voted"
    else:
        # Create new vote
        new_vote = MealVote()
        new_vote.meal_id = meal_id_int
        new_vote.client_id = client_id
        new_vote.date = today
        new_vote.vote_type = vote_type
        db.session.add(new_vote)
        db.session.commit()
        message = "Vote recorded"

    # Get updated vote counts
    vote_counts = get_vote_counts(meal_id)

    # Create response with cookie
    response = make_response(jsonify({"message": message, "votes": vote_counts}))

    # Set client ID cookie (expires in 1 year)
    set_client_id_cookie(response, client_id)

    return response


# API route to get vote counts for a meal
@app.route("/api/votes/<int:meal_id>", methods=["GET"])
def get_votes(meal_id):
    meal = db.session.get(Meal, meal_id)
    if not meal:
        return jsonify({"error": "Meal not found"}), 404

    # Get client ID from cookie if exists
    client_id = get_client_id()

    # Get vote counts
    vote_counts = get_vote_counts(meal_id)

    # Check if client has already voted
    has_voted = has_voted_today(meal_id, client_id)

    # Create response with cookie
    response = make_response(jsonify({"votes": vote_counts, "has_voted": has_voted}))

    # Set client ID cookie if new
    if not request.cookies.get("client_id"):
        set_client_id_cookie(response, client_id)

    return response


@app.route("/api/comments/<int:meal_id>", methods=["GET"])
def get_comments(meal_id):
    meal = db.session.get(Meal, meal_id)
    if not meal:
        return jsonify({"error": "Meal not found"}), 404

    language = normalize_language(request.args.get("lang", DEFAULT_LANGUAGE))
    try:
        limit = int(request.args.get("limit", COMMENTS_DEFAULT_LIMIT))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid pagination"}), 400

    limit = max(1, min(COMMENTS_MAX_LIMIT, limit))
    offset = max(0, offset)

    query = MealComment.query.filter_by(meal_id=meal_id).order_by(
        MealComment.created_at.desc(), MealComment.id.desc()
    )
    total = query.count()
    comments = query.offset(offset).limit(limit).all()

    return jsonify(
        {
            "comments": [serialize_comment(comment, language) for comment in comments],
            "count": total,
            "has_more": offset + len(comments) < total,
        }
    )


@app.route("/api/comments", methods=["POST"])
def create_comment():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": translate(DEFAULT_LANGUAGE, "api_invalid_json")}), 400

    meal_id = data.get("meal_id")
    rating = str(data.get("rating", "")).strip().lower()
    author_name = str(data.get("author_name", "") or "").strip()
    comment_text = str(data.get("text", "") or "").strip()
    language = normalize_language(data.get("lang", DEFAULT_LANGUAGE))

    if rating not in {"good", "bad"}:
        return jsonify({"error": translate(language, "api_invalid_comment_rating")}), 400
    if len(author_name) > COMMENT_AUTHOR_MAX_LENGTH:
        return jsonify({"error": translate(language, "api_comment_name_too_long")}), 400
    if len(comment_text) > COMMENT_TEXT_MAX_LENGTH:
        return jsonify({"error": translate(language, "api_comment_text_too_long")}), 400

    try:
        meal_id_int = int(meal_id)
    except (TypeError, ValueError):
        return jsonify({"error": translate(language, "api_invalid_comment_meal")}), 400

    meal = db.session.get(Meal, meal_id_int)
    if not meal:
        return jsonify({"error": translate(language, "api_comment_meal_not_found")}), 404

    client_id = get_client_id()
    translated = {"de": "", "en": "", "translation_failed": False}
    if comment_text:
        try:
            translated = translate_comment_text(comment_text, language)
        except MPSAuthenticationError:
            logger.warning("Comment translation auth failed; saving original text only.")
            translated = {
                "de": comment_text if language == "de" else "",
                "en": comment_text if language == "en" else "",
                "translation_failed": True,
            }

    comment = MealComment()
    comment.meal_id = meal_id_int
    comment.client_id = client_id
    comment.rating = rating
    comment.author_name = author_name or None
    comment.source_language = language
    comment.text_de = translated.get("de") or None
    comment.text_en = translated.get("en") or None
    comment.translation_failed = bool(translated.get("translation_failed"))

    db.session.add(comment)
    db.session.commit()
    db.session.refresh(comment)

    response = make_response(
        jsonify(
            {
                "message": translate(language, "comment_saved"),
                "comment": serialize_comment(comment, language),
                "count": get_comment_count(meal_id_int),
            }
        )
    )
    set_client_id_cookie(response, client_id)
    return response, 201


@app.route("/api/meal_image", methods=["GET"])
def get_meal_image():
    language = resolve_language(request)
    texts = get_translations(language)
    meal_id = request.args.get("meal_id", type=int)
    mensa_name = (request.args.get("mensa") or "").strip()
    selected_date = (request.args.get("date") or "").strip()

    if not meal_id or not mensa_name or not selected_date:
        return jsonify({"error": texts["api_invalid_meal_image_request"]}), 400

    meal = db.session.get(Meal, meal_id)
    if meal is None:
        return jsonify({"error": texts["api_comment_meal_not_found"]}), 404

    try:
        image_result = find_or_cache_meal_image(
            meal,
            mensa_name,
            selected_date,
            MEAL_IMAGE_NEGATIVE_LOOKUP_TTL_SECONDS,
        )
    except ValueError:
        return jsonify({"error": texts["api_invalid_meal_image_request"]}), 400
    except (requests.RequestException, StudiFutterError) as e:
        logger.warning("StudiFutter image lookup failed: %s", e)
        return jsonify({"error": texts["api_meal_image_lookup_failed"]}), 502

    if not image_result:
        return jsonify(
            {
                "found": False,
                "message": texts["meal_image_unavailable"],
            }
        )

    return jsonify({"found": True, **image_result})


@app.route("/api/studifutter/assets/<file_id>", methods=["GET"])
def proxy_studifutter_asset(file_id):
    if not is_directus_file_id(file_id):
        return jsonify({"error": "Invalid asset id"}), 400

    variant = (request.args.get("variant") or FULL_VARIANT).strip().lower()

    try:
        asset = get_cached_studifutter_asset(file_id, variant=variant)
    except MealImageCacheInvalidRequest as e:
        return jsonify({"error": str(e)}), 400
    except (requests.RequestException, MealImageCacheError) as e:
        logger.warning("StudiFutter asset proxy failed for %s: %s", file_id, e)
        return jsonify({"error": "Unable to load asset"}), 502

    response = send_file(
        asset.path,
        mimetype=asset.content_type,
        conditional=True,
        max_age=31536000,
    )
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def clean_recommendation_text(recommendation):
    """Normalize common wrapping added by chat models."""
    recommendation = recommendation.strip()

    if recommendation.startswith("```json"):
        recommendation = recommendation[len("```json") :].rstrip("`").strip()
    elif recommendation.startswith("```"):
        recommendation = recommendation[len("```") :].rstrip("`").strip()

    common_phrases_to_remove = [
        "Hier ist deine Empfehlung:",
        "Meine Empfehlung lautet:",
        "Empfehlung:",
        "Here is your recommendation:",
        "My recommendation is:",
        "Recommendation:",
    ]
    for phrase in common_phrases_to_remove:
        if recommendation.lower().startswith(phrase.lower()):
            recommendation = recommendation[len(phrase) :].strip()

    return recommendation.strip()


@app.route("/api/get_recommendation", methods=["POST"])
def get_recommendation():
    """Get a unified meal recommendation from the configured AI provider."""
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify(
                {"error": translate(DEFAULT_LANGUAGE, "api_invalid_json")}
            ), 400
        available_meals = data.get("meals", [])
        mensa = str(data.get("mensa", "")).strip()
        recommender = str(data.get("recommender", "")).strip()
        language = normalize_language(data.get("lang", DEFAULT_LANGUAGE))

        if not available_meals:
            return jsonify({"error": translate(language, "api_no_meals")}), 400
        if not mensa:
            return jsonify({"error": translate(language, "api_no_mensa")}), 400
        if not recommender:
            return jsonify({"error": translate(language, "api_no_recommender")}), 400

        recommender = recommender[:80]

        meal_list_for_prompt = "\n".join([f"- {meal}" for meal in available_meals])

        if not has_configured_mps_api_key():
            logger.error(
                "OPENROUTER_API_KEY not found in environment for recommendation."
            )
            return jsonify(
                {"error": translate(language, "api_openrouter_key_missing")}
            ), 500
        api_key = os.environ.get("OPENROUTER_API_KEY")

        prompt_template = get_recommendation_prompt(language, recommender)
        prompt = (
            prompt_template.replace("{meal_list}", meal_list_for_prompt)
            .replace("{mensa}", mensa)
            .replace("{recommender}", recommender)
        )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        response = requests.post(
            get_openrouter_base_url(),
            headers=headers,
            json={
                "model": get_ai_model_max(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.1,
                "max_tokens": get_ai_max_tokens_max(),
            },
            timeout=45,
        )

        if response.status_code == 200:
            result = response.json()
            recommendation = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            recommendation_html = markdown_to_html(
                clean_recommendation_text(recommendation)
            )

            return jsonify({"recommendation": recommendation_html})
        else:
            logger.error(
                f"Recommendation OpenRouter API error: {response.status_code} - {response.text}"
            )
            return jsonify(
                {
                    "error": translate(language, "api_openrouter_error"),
                    "details": response.text,
                }
            ), 500

    except Exception as e:
        logger.error(f"Error in get_recommendation: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/get_mps_score", methods=["POST"])
def get_mps_score():
    """Get Max Pumper Score for a meal using OpenRouter."""
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify(
                {"error": translate(DEFAULT_LANGUAGE, "api_invalid_json")}
            ), 400

        meal_description = data.get("meal_description", "")
        if not meal_description:
            return jsonify({"error": "No meal description provided"}), 400

        if not has_configured_mps_api_key():
            logger.error(
                "OPENROUTER_API_KEY not found in environment for MPS calculation."
            )
            return jsonify({"error": "OpenRouter API key not configured"}), 500

        try:
            mps_score = calculate_mps_for_meal(meal_description)
        except MPSAuthenticationError:
            return jsonify({"error": "OpenRouter rejected API key"}), 500

        if mps_score is None:
            return jsonify({"error": "Unable to calculate MPS score"}), 500

        return jsonify({"mps_score": mps_score})

    except Exception as e:
        logger.error(f"Error in get_mps_score: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
