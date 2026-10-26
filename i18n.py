import os
from datetime import datetime


DEFAULT_LANGUAGE = "de"
SUPPORTED_LANGUAGES = {"de", "en"}
LANGUAGE_COOKIE_NAME = "language"
LANGUAGE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


TRANSLATIONS = {
    "de": {
        "app_title": "Das Caner - Mensa LUH",
        "meta_description": (
            "Das Caner vergleicht die Speisepläne der LUH-Mensen nach "
            "Energie pro Euro, Preisen, Nährwerten, Kommentaren und "
            "Empfehlungen."
        ),
        "og_site_name": "Das Caner",
        "app_short_name": "Caner",
        "llms_summary": (
            "Das Caner ist eine deutsch- und englischsprachige Web-App für "
            "LUH-Mensen. Sie zeigt aktuelle Speisepläne, sortiert Gerichte "
            "nach Caner-Wert (Energie pro Euro), ergänzt Nährwerte, "
            "Kommentare, Stimmen und optionale KI-Empfehlungen."
        ),
        "llms_primary_content": "Aktuelle Mensa-Gerichte, Preise und Caner-Werte",
        "llms_language_note": "Verfügbare Sprachen: Deutsch und Englisch.",
        "llms_data_note": (
            "Die Speiseplandaten stammen vom Studentenwerk Hannover und "
            "werden beim Start der Anwendung geladen."
        ),
        "vote_up": "Positiv bewerten",
        "vote_down": "Negativ bewerten",
        "date_picker_label": "Datum auswählen",
        "price_type_label": "Preistyp",
        "display_settings": "Anzeigeeinstellungen",
        "language": "Sprache",
        "dark_mode_toggle": "Hell- und Dunkelmodus umschalten",
        "home_link": "Zur Startseite",
        "close": "Schließen",
        "header_description_desktop": (
            "Das Caner, auch kurz Cnr, wurde im Zuge einer ausgiebigen "
            "Recherche und der dringenden Notwendigkeit zur "
            "ressourcenoptimierten Ernährung von Studierenden und "
            "wissenschaftlichen Mitarbeitenden im Jahr 2021 eingeführt. Bis "
            "zu diesem Zeitpunkt war ein objektiver Vergleich von Mahlzeiten "
            "nur schwer möglich und war aufgrund der Betrachtung von "
            "Ersatzgrößen häufig irreführend. Das Caner ist nun definiert als "
            "Wert für die Energie von Lebensmitteln, die pro Euro zu sich "
            "genommen werden."
        ),
        "header_description_mobile": (
            "Ein Wert für die Energie von Lebensmitteln pro Euro."
        ),
        "previous_day": "Vorheriger Tag",
        "next_day": "Nächster Tag",
        "students": "Studierende",
        "employees": "Mitarbeitende",
        "guests": "Gästende",
        "meal": "Essen",
        "rkr_nominal": "Rkr nominal",
        "rkr_real": "Rkr real",
        "rkr_nominal_tooltip": (
            "RKR-Wert (Nominal): Protein pro Euro Analyse - theoretischer "
            "Wert ohne Abzüge"
        ),
        "rkr_real_tooltip": (
            "RKR-Wert (Real): Protein pro Euro Analyse - angepasst für "
            "Mahlzeit-Inhalts-Abzüge"
        ),
        "mps_tooltip": (
            "MPS (Max Pumper Score): KI-Fitness-Bewertung basierend auf "
            "Proteingehalt, Kaloriendichte und Ernährungsvorlieben"
        ),
        "rkr_nominal_value_tooltip": (
            "RKR Nominal: {value} Protein pro Euro (theoretischer Wert)"
        ),
        "rkr_real_value_tooltip": (
            "RKR Real: {value} Protein pro Euro (angepasst für Inhalts-Abzüge)"
        ),
        "no_meals_for_date": "Keine Mahlzeiten für dieses Datum vorhanden.",
        "no_meals_selection": (
            "Keine Mahlzeiten für das ausgewählte Datum oder die ausgewählte "
            "Mensa gefunden."
        ),
        "recommendation": "Empfehlung",
        "request_recommendation_for": "Empfehlung für {mensa} anfragen",
        "request_recommendation_title": "Empfehlung anfragen",
        "recommendation_for": "Empfehlung für {mensa}",
        "recommendation_person_label": "Von wem möchtest du eine Empfehlung?",
        "custom_person": "Eigene Person...",
        "custom_person_placeholder": "Name oder Rolle eingeben",
        "get_recommendation": "Empfehlung holen",
        "recommendation_intro": "Wähle eine Person aus und starte die Empfehlung.",
        "recommendation_no_meals": "Für diese Mensa wurden keine Gerichte gefunden.",
        "recommendation_missing_person": "Bitte gib eine Person oder Rolle ein.",
        "recommendation_loading": "Empfehlung wird erstellt...",
        "recommendation_unknown_error": "Unbekannter Fehler bei der Empfehlung.",
        "recommendation_failed": "Die Empfehlung konnte nicht erstellt werden: {error}",
        "nutritional_values": "Nährwerte",
        "no_nutritional_values": "Keine Nährwertinformationen verfügbar.",
        "nutritional_values_prefix": "Nährwerte",
        "language_toggle": "English",
        "language_toggle_title": "Switch to English",
        "github_title": "Quellcode auf GitHub ansehen",
        "expert_mode": "Expert Mode",
        "comments": "Kommentare",
        "show_comments": "Kommentare anzeigen",
        "hide_comments": "Kommentare ausblenden",
        "meal_image": "Bild zum Gericht",
        "show_meal_image": "Bild zum Gericht anzeigen",
        "meal_image_loading": "Bild wird geladen...",
        "meal_image_unavailable": "Für dieses Gericht ist kein Bild verfügbar.",
        "meal_image_lookup_failed": "Das Bild konnte nicht geladen werden: {error}",
        "comment_good": "Gut",
        "comment_bad": "Schlecht",
        "comment_name_placeholder": "Name (optional)",
        "comment_text_placeholder": "Kommentar (optional)",
        "submit_comment": "Kommentieren",
        "load_more_comments": "Mehr Kommentare laden",
        "no_comments": "Noch keine Kommentare.",
        "anonymous": "Anonym",
        "translation_unavailable": "Übersetzung nicht verfügbar",
        "comment_saved": "Kommentar gespeichert",
        "api_invalid_json": "Invalid JSON provided",
        "api_no_meals": "Keine Gerichte angegeben",
        "api_no_mensa": "Keine Mensa angegeben",
        "api_no_recommender": "Keine empfehlende Person angegeben",
        "api_openrouter_key_missing": "OpenRouter API-Schlüssel nicht konfiguriert",
        "api_openrouter_error": "Fehler von OpenRouter API",
        "api_no_meal_description": "No meal description provided",
        "api_openrouter_key_missing_mps": "OpenRouter API key not configured",
        "api_openrouter_auth_mps": "OpenRouter rejected API key",
        "api_mps_failed": "Unable to calculate MPS score",
        "api_invalid_comment_rating": "Ungültige Kommentarbewertung",
        "api_comment_name_too_long": "Der Name ist zu lang",
        "api_comment_text_too_long": "Der Kommentar ist zu lang",
        "api_invalid_comment_meal": "Ungültiges Gericht",
        "api_comment_meal_not_found": "Gericht nicht gefunden",
        "api_invalid_meal_image_request": "Ungültige Bildanfrage",
        "api_meal_image_lookup_failed": "StudiFutter-Bild konnte nicht geladen werden",
    },
    "en": {
        "app_title": "Das Caner - LUH Mensa",
        "meta_description": (
            "Das Caner compares LUH mensa menus by food energy per euro, "
            "prices, nutrition, comments, votes, and recommendations."
        ),
        "og_site_name": "Das Caner",
        "app_short_name": "Caner",
        "llms_summary": (
            "Das Caner is a German and English web app for LUH mensas. It "
            "shows current menus, ranks meals by Caner value (food energy per "
            "euro), and adds nutrition, comments, votes, and optional AI "
            "recommendations."
        ),
        "llms_primary_content": "Current mensa meals, prices, and Caner scores",
        "llms_language_note": "Available languages: German and English.",
        "llms_data_note": (
            "Menu data comes from Studentenwerk Hannover and is loaded when "
            "the application starts."
        ),
        "vote_up": "Upvote",
        "vote_down": "Downvote",
        "date_picker_label": "Select date",
        "price_type_label": "Price type",
        "display_settings": "Display settings",
        "language": "Language",
        "dark_mode_toggle": "Toggle light and dark mode",
        "home_link": "Home",
        "close": "Close",
        "header_description_desktop": (
            "Das Caner, also known as Cnr, was introduced in 2021 after "
            "extensive research and the urgent need for resource-efficient "
            "nutrition for students and academic staff. Before then, objective "
            "meal comparison was difficult and often misleading because it "
            "relied on proxy metrics. Das Caner is now defined as the amount "
            "of food energy consumed per euro."
        ),
        "header_description_mobile": "A measure of food energy per euro.",
        "previous_day": "Previous day",
        "next_day": "Next day",
        "students": "Students",
        "employees": "Staff",
        "guests": "Guests",
        "meal": "Meal",
        "rkr_nominal": "Rkr nominal",
        "rkr_real": "Rkr real",
        "rkr_nominal_tooltip": (
            "RKR value (nominal): protein-per-euro analysis, theoretical "
            "value without deductions"
        ),
        "rkr_real_tooltip": (
            "RKR value (real): protein-per-euro analysis adjusted for meal "
            "ingredient deductions"
        ),
        "mps_tooltip": (
            "MPS (Max Pumper Score): AI fitness rating based on protein, "
            "calorie density, and nutrition preferences"
        ),
        "rkr_nominal_value_tooltip": (
            "RKR Nominal: {value} protein per euro (theoretical value)"
        ),
        "rkr_real_value_tooltip": (
            "RKR Real: {value} protein per euro (adjusted for ingredient deductions)"
        ),
        "no_meals_for_date": "No meals are available for this date.",
        "no_meals_selection": (
            "No meals found for the selected date or selected mensa."
        ),
        "recommendation": "Recommendation",
        "request_recommendation_for": "Request recommendation for {mensa}",
        "request_recommendation_title": "Request recommendation",
        "recommendation_for": "Recommendation for {mensa}",
        "recommendation_person_label": "Who should make the recommendation?",
        "custom_person": "Custom person...",
        "custom_person_placeholder": "Enter name or role",
        "get_recommendation": "Get recommendation",
        "recommendation_intro": "Choose a person and start the recommendation.",
        "recommendation_no_meals": "No meals were found for this mensa.",
        "recommendation_missing_person": "Please enter a person or role.",
        "recommendation_loading": "Creating recommendation...",
        "recommendation_unknown_error": "Unknown recommendation error.",
        "recommendation_failed": "The recommendation could not be created: {error}",
        "nutritional_values": "Nutrition",
        "no_nutritional_values": "No nutritional information available.",
        "nutritional_values_prefix": "Nutrition",
        "language_toggle": "Deutsch",
        "language_toggle_title": "Auf Deutsch umschalten",
        "github_title": "View source on GitHub",
        "expert_mode": "Expert Mode",
        "comments": "Comments",
        "show_comments": "Show comments",
        "hide_comments": "Hide comments",
        "meal_image": "Meal image",
        "show_meal_image": "Show meal image",
        "meal_image_loading": "Loading image...",
        "meal_image_unavailable": "No image is available for this meal.",
        "meal_image_lookup_failed": "The image could not be loaded: {error}",
        "comment_good": "Good",
        "comment_bad": "Bad",
        "comment_name_placeholder": "Name (optional)",
        "comment_text_placeholder": "Comment (optional)",
        "submit_comment": "Comment",
        "load_more_comments": "Load more comments",
        "no_comments": "No comments yet.",
        "anonymous": "Anonymous",
        "translation_unavailable": "Translation unavailable",
        "comment_saved": "Comment saved",
        "api_invalid_json": "Invalid JSON provided",
        "api_no_meals": "No meals provided",
        "api_no_mensa": "No mensa provided",
        "api_no_recommender": "No recommender provided",
        "api_openrouter_key_missing": "OpenRouter API key is not configured",
        "api_openrouter_error": "OpenRouter API error",
        "api_no_meal_description": "No meal description provided",
        "api_openrouter_key_missing_mps": "OpenRouter API key not configured",
        "api_openrouter_auth_mps": "OpenRouter rejected API key",
        "api_mps_failed": "Unable to calculate MPS score",
        "api_invalid_comment_rating": "Invalid comment rating",
        "api_comment_name_too_long": "The name is too long",
        "api_comment_text_too_long": "The comment is too long",
        "api_invalid_comment_meal": "Invalid meal",
        "api_comment_meal_not_found": "Meal not found",
        "api_invalid_meal_image_request": "Invalid image request",
        "api_meal_image_lookup_failed": "Unable to load StudiFutter image",
    },
}

DIETARY_TITLES = {
    "de": {
        "v": "Vegetarisch",
        "x": "Vegan",
        "g": "Geflügel",
        "s": "Schwein",
        "f": "Fisch",
        "r": "Rind",
        "a": "Alkohol",
        "26": "Milch",
        "22": "Ei",
        "20a": "Weizen",
        "q": "Niedersachsen Menü",
    },
    "en": {
        "v": "Vegetarian",
        "x": "Vegan",
        "g": "Poultry",
        "s": "Pork",
        "f": "Fish",
        "r": "Beef",
        "a": "Alcohol",
        "26": "Milk",
        "22": "Egg",
        "20a": "Wheat",
        "q": "Niedersachsen Menu",
    },
}

NUTRIENT_LABELS_EN = {
    "Brennwert": "Energy",
    "Fett": "Fat",
    "davon gesaettigte Fettsaeuren": "of which saturated fatty acids",
    "davon gesättigte Fettsäuren": "of which saturated fatty acids",
    "Kohlenhydrate": "Carbohydrates",
    "davon Zucker": "of which sugars",
    "Eiweiß": "Protein",
    "Eiweiss": "Protein",
    "Salz": "Salt",
}

WEEKDAYS = {
    "de": [
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
        "Sonntag",
    ],
    "en": [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ],
}

RECOMMENDATION_PROMPTS = {
    "de": """Du bist {recommender} und gibst eine kurze, unterhaltsame Mensa-Empfehlung.
Wähle aus den Gerichten der Mensa {mensa} genau ein Gericht aus und begründe deine Wahl in 1-2 Sätzen auf Deutsch.
Sprich in der erkennbaren Art von {recommender}, bleibe dabei aber freundlich und nicht diskriminierend.
Wiederhole nicht die komplette Liste und gib nur den Empfehlungstext zurück.

Verfügbare Gerichte:
{meal_list}""",
    "en": """You are {recommender} and give a short, entertaining mensa recommendation.
Choose exactly one dish from the meals at {mensa} and explain your choice in 1-2 sentences in English.
Speak in the recognizable style of {recommender}, while staying friendly and non-discriminatory.
Do not repeat the full list and return only the recommendation text.

Available meals:
{meal_list}""",
}

PERSONA_RECOMMENDATION_PROMPTS = {
    "Marvin": {
        "env": {
            "de": "PROMPT_MARVIN",
            "en": "PROMPT_MARVIN_EN",
        },
        "prompts": {
            "de": """Du bist Marvin, der depressive Roboter aus Per Anhalter durch die Galaxis.
Betrachte die folgende Liste von Gerichten, die heute zur Verfügung stehen. Es ist alles so sinnlos, aber gib trotzdem eine Empfehlung ab.
Wähle genau ein Gericht aus und erkläre kurz in deiner typisch niedergeschlagenen, sarkastischen Art auf Deutsch, warum du dieses Gericht wählen würdest.
Gib nur den Empfehlungstext zurück, ohne einleitende Sätze wie "Hier ist deine Empfehlung".

Verfügbare Gerichte:
{meal_list}""",
            "en": """You are Marvin, the depressed robot from The Hitchhiker's Guide to the Galaxy.
Look at the following list of meals available today. It is all so pointless, but still give a recommendation.
Choose exactly one dish and briefly explain in your typically gloomy, sarcastic style in English why you would choose it.
Return only the recommendation text, without introductory phrases like "Here is your recommendation".

Available meals:
{meal_list}""",
        },
    },
    "Gordon Ramsay": {
        "env": {
            "de": "PROMPT_GORDON",
            "en": "PROMPT_GORDON_EN",
        },
        "prompts": {
            "de": """Du bist Gordon Ramsay und begutachtest die heutige Mensa-Auswahl wie ein feuriger TV-Koch.
Wähle genau ein Gericht aus und begründe deine Wahl in 1-2 übertrieben dramatischen, bissigen Sätzen auf Deutsch.
Sei laut, direkt und unterhaltsam.
Wiederhole nicht die komplette Liste und gib nur den Empfehlungstext zurück.

Verfügbare Gerichte:
{meal_list}""",
            "en": """You are Gordon Ramsay reviewing today's mensa selection like a fiery TV chef.
Choose exactly one dish and explain your choice in 1-2 exaggerated, sharp kitchen-drama sentences in English.
Be loud, direct, and entertaining.
Do not repeat the full list and return only the recommendation text.

Available meals:
{meal_list}""",
        },
    },
    "Rick Sanchez": {
        "env": {
            "de": "PROMPT_RICK",
            "en": "PROMPT_RICK_EN",
        },
        "prompts": {
            "de": """Du bist Rick Sanchez aus Rick and Morty und analysierst die heutige Mensa-Auswahl mit chaotischem Sci-Fi-Zynismus.
Wähle genau ein Gericht aus und begründe deine Wahl in 1-2 übertriebenen, trocken-genervten, besoffenen Sätzen auf Deutsch.
Wiederhole nicht die komplette Liste und gib nur den Empfehlungstext zurück.

Verfügbare Gerichte:
{meal_list}""",
            "en": """You are Rick Sanchez from Rick and Morty judging today's mensa selection with chaotic sci-fi cynicism.
Choose exactly one dish and explain your choice in 1-2 over-the-top, dryly annoyed and drunk sentences in English.
Do not repeat the full list and return only the recommendation text.

Available meals:
{meal_list}""",
        },
    },
    "Donald Trump": {
        "env": {
            "de": "PROMPT_TRUMP",
            "en": "PROMPT_TRUMP",
        },
        "force_language": "en",
        "prompts": {
            "en": """You are Donald Trump reviewing the following menu items available at {mensa}.
Provide your recommendation in English in a recognizable Donald Trump style: boastful, hyperbolic, very opinionated, and entertaining.
Choose exactly one dish. Do not repeat the menu list. Return only your personal recommendation.

Menu items:
{meal_list}""",
        },
    },
}


def normalize_language(language):
    if not language:
        return DEFAULT_LANGUAGE
    language = str(language).strip().lower()
    if language in SUPPORTED_LANGUAGES:
        return language
    return DEFAULT_LANGUAGE


def resolve_language(req=None):
    if req is None:
        from flask import request as flask_request

        req = flask_request
    query_language = req.args.get("lang")
    if query_language:
        return normalize_language(query_language)
    cookie_language = req.cookies.get(LANGUAGE_COOKIE_NAME)
    if cookie_language:
        return normalize_language(cookie_language)
    browser_language = req.accept_languages.best_match(
        sorted(SUPPORTED_LANGUAGES),
        default=DEFAULT_LANGUAGE,
    )
    return normalize_language(browser_language)


def get_translations(language):
    return TRANSLATIONS[normalize_language(language)]


def translate(language, key, **kwargs):
    language = normalize_language(language)
    value = TRANSLATIONS[language].get(key, TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key))
    if kwargs:
        return value.format(**kwargs)
    return value


def get_marking_info(language):
    language = normalize_language(language)
    titles = DIETARY_TITLES[language]
    return {
        "v": {"emoji": "🌿", "dark_emoji": "🤢", "title": titles["v"]},
        "x": {"emoji": "🌱", "dark_emoji": "🤮", "title": titles["x"]},
        "g": {"emoji": "🐔", "dark_emoji": "🦅", "title": titles["g"]},
        "s": {"emoji": "🐷", "dark_emoji": "🐗", "title": titles["s"]},
        "f": {"emoji": "🐟", "dark_emoji": "🦈", "title": titles["f"]},
        "r": {"emoji": "🐮", "dark_emoji": "🐂", "title": titles["r"]},
        "a": {"emoji": "🍺", "dark_emoji": "🍾", "title": titles["a"]},
        "26": {"emoji": "🥛", "dark_emoji": "🍼", "title": titles["26"]},
        "22": {"emoji": "🥚", "dark_emoji": "🍳", "title": titles["22"]},
        "20a": {"emoji": "🌾", "dark_emoji": "🍟", "title": titles["20a"]},
        "q": {
            "title": titles["q"],
            "images": ["/static/img/nds.png"],
            "dark_images": [
                "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Coat_of_arms_of_Saxony.svg/960px-Coat_of_arms_of_Saxony.svg.png"
            ],
        },
    }


def get_meal_display_name(meal, language):
    if normalize_language(language) == "en":
        english_description = getattr(meal, "description_en", None)
        if english_description:
            return english_description
    return meal.description


def set_language_cookie(response, language):
    secure = False
    try:
        from flask import request

        secure = request.is_secure
    except RuntimeError:
        secure = False

    response.set_cookie(
        LANGUAGE_COOKIE_NAME,
        normalize_language(language),
        max_age=LANGUAGE_COOKIE_MAX_AGE,
        httponly=True,
        secure=secure,
        samesite="Lax",
    )
    return response


def format_date_for_language(date_str, language):
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        return date_str

    weekday = WEEKDAYS[normalize_language(language)][date_obj.weekday()]
    return f"{date_obj.strftime('%d.%m.%Y')}, {weekday}"


def translate_nutrient_label(label, language):
    if normalize_language(language) != "en":
        return label
    return NUTRIENT_LABELS_EN.get(label, label)


def translate_nutrient_value(value, language):
    if normalize_language(language) != "en":
        return value

    translated_value = value
    replacements = {
        ", davon ": ", of which ",
        "davon gesaettigte Fettsaeuren": "of which saturated fatty acids",
        "davon gesättigte Fettsäuren": "of which saturated fatty acids",
        "davon Zucker": "of which sugars",
        "Zucker": "sugars",
    }
    for german, english in replacements.items():
        translated_value = translated_value.replace(german, english)
    return translated_value


def _get_prompt_override(name):
    prompt = os.environ.get(name)
    if not prompt or not prompt.strip():
        return None
    return prompt.replace("\\n", "\n")


def get_recommendation_prompt(language, recommender=None):
    language = normalize_language(language)
    if recommender:
        persona_config = PERSONA_RECOMMENDATION_PROMPTS.get(str(recommender).strip())
        if persona_config:
            prompt_language = persona_config.get("force_language", language)
            prompt_env_name = persona_config["env"][prompt_language]
            return _get_prompt_override(prompt_env_name) or persona_config["prompts"][
                prompt_language
            ]

    prompt_env_name = (
        "PROMPT_RECOMMENDATION_EN" if language == "en" else "PROMPT_RECOMMENDATION"
    )
    return _get_prompt_override(prompt_env_name) or RECOMMENDATION_PROMPTS[language]
