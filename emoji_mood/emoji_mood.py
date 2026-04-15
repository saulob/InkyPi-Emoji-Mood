import random
import logging
import os
import json
from datetime import datetime
import pytz
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

# Pin to a specific Twemoji release for reproducible rendering.
# Using `@latest` can cause snapshots or rendering to change unexpectedly
# when the upstream assets are updated. Update this tag intentionally
# when you want to bump Twemoji, or vendor the assets locally for full
# reproducibility.
TWEMOJI_RELEASE = "14.0.2"
TWEMOJI_BASE_URL = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@{TWEMOJI_RELEASE}/assets/svg"

# Supported translation language codes. Keep this set in sync with files in translations/.
SUPPORTED_LANGUAGES = {"en", "pt", "pt-br", "es", "fr", "de", "it", "nl", "id"}


def _emoji_to_twemoji_url(emoji):
    """Convert a Unicode emoji string to a Twemoji CDN SVG URL."""
    codepoints = "-".join(
        f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F
    )
    return f"{TWEMOJI_BASE_URL}/{codepoints}.svg"


def _get_smart_mood(tz):
    """Select a mood based on current time and day of week with weighted probabilities.
    
    Returns a dict with:
    - mood: selected mood key
    - time_period: morning/afternoon/evening/night
    - weekday_name: Monday/Tuesday/etc
    - selected_weight: weight value of chosen mood
    """
    try:
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # For late night hours (00:00-04:59), use previous day for weekday-based weighting
    # to make mood selection feel more natural for late night usage
    if hour < 5:
        weekday = (weekday - 1) % 7
    
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_name = weekday_names[weekday]
    
    # Determine time period
    if 5 <= hour < 12:
        time_period = "morning"
    elif 12 <= hour < 17:
        time_period = "afternoon"
    elif 17 <= hour < 21:
        time_period = "evening"
    else:
        time_period = "night"
    
    # Base weight of 1 for all moods
    mood_weights = {
        "happy": 1,
        "neutral": 1,
        "low_energy": 1,
        "stress": 1,
        "fun": 1,
        "weird": 1,
        "focus": 1,
        "adventure": 1,
        "love": 1,
        "sick": 1,
    }
    
    # Incrementally adjust weights based on time period (+1 or +2)
    if time_period == "morning":
        mood_weights["focus"] += 2
        mood_weights["happy"] += 1
        mood_weights["neutral"] += 1
    elif time_period == "afternoon":
        mood_weights["focus"] += 2
        mood_weights["neutral"] += 1
        mood_weights["stress"] += 1
    elif time_period == "evening":
        mood_weights["fun"] += 2
        mood_weights["love"] += 1
        mood_weights["low_energy"] += 1
    else:  # night
        mood_weights["low_energy"] += 2
        mood_weights["weird"] += 1
        mood_weights["neutral"] += 1
    
    # Incrementally adjust weights based on weekday (+1 or +2)
    # For late night (00:00-04:59), weekday is already adjusted to previous day above
    if weekday == 0:  # Monday
        mood_weights["focus"] += 2
        mood_weights["stress"] += 1
    elif weekday == 4:  # Friday
        mood_weights["happy"] += 2
        mood_weights["fun"] += 1
    elif weekday == 5:  # Saturday
        mood_weights["fun"] += 2
        mood_weights["adventure"] += 1
        mood_weights["love"] += 1
    elif weekday == 6:  # Sunday
        mood_weights["low_energy"] += 1
        mood_weights["love"] += 1
        mood_weights["neutral"] += 1
    
    # Small random boost for all moods to keep variety and avoid rigid patterns
    for mood in mood_weights:
        mood_weights[mood] += random.random() * 0.3
    
    # Select mood using weighted random choice
    moods = list(mood_weights.keys())
    weights = [mood_weights[mood] for mood in moods]
    selected_mood = random.choices(moods, weights=weights, k=1)[0]
    selected_weight = mood_weights[selected_mood]
    
    return {
        "mood": selected_mood,
        "time_period": time_period,
        "weekday_name": weekday_name,
        "selected_weight": round(selected_weight, 1),
    }

MOOD_DATA = {
    "happy": {
        "emojis": [
            "😀", "😃", "😄", "😁", "😆", "😅", "🙂", "😊", "😇", "🥳",
        ],
        "captions": [
            "Good vibes today",
            "Feeling bright",
            "A cheerful moment",
            "Smile mode on",
            "Everything feels right",
            "Light and easy day",
            "Positive energy",
            "Keep smiling",
            "Good mood activated",
            "Today is a good day",
        ],
    },
    "neutral": {
        "emojis": [
            "🙂", "😐", "😶", "😑", "🤔", "🧐", "🤓", "😌", "🙄", "😏",
        ],
        "captions": [
            "Just cruising",
            "Steady and calm",
            "Nothing dramatic today",
            "Balanced mood",
            "Taking it easy",
            "All good, no rush",
            "Simple day ahead",
            "Calm and collected",
            "Neutral vibes",
            "Going with the flow",
        ],
    },
    "low_energy": {
        "emojis": [
            "😴", "😪", "😌", "😔", "😕", "😞", "😟", "😓", "😥", "🫠",
        ],
        "captions": [
            "Take it slow",
            "Quiet energy today",
            "Easy pace",
            "Recharge mode",
            "Low battery vibes",
            "Rest a bit more",
            "Slow but steady",
            "Take a break",
            "Energy saving mode",
            "Just getting through",
        ],
    },
    "stress": {
        "emojis": [
            "😤", "😠", "😡", "😣", "😖", "😫", "😩", "🤯", "😵", "😵‍💫",
        ],
        "captions": [
            "A lot going on",
            "Take a breath",
            "Messy but moving",
            "One step at a time",
            "Too much today",
            "Keep pushing",
            "Stay strong",
            "Breathe and focus",
            "Handling chaos",
            "Survive and move",
        ],
    },
    "fun": {
        "emojis": [
            "🎮", "🎲", "🎉", "🎈", "🍕", "🍔", "🌭", "🍟", "🎬", "🎥",
        ],
        "captions": [
            "Time to have fun",
            "Play mode on",
            "Enjoy the moment",
            "Just for fun",
            "Take a break and play",
            "Good time ahead",
            "Relax and enjoy",
            "Fun vibes only",
            "Let loose a bit",
            "Today is for fun",
        ],
    },
    "weird": {
        "emojis": [
            "🤡", "👽", "👻", "💀", "👹", "👺", "🤖", "👾", "🥸", "💩",
        ],
        "captions": [
            "Feeling weird today",
            "Something is off",
            "Strange vibes",
            "Not a normal day",
            "Embrace the chaos",
            "A bit unusual",
            "Weird but okay",
            "Glitch in the mood",
            "Unexpected energy",
            "Just roll with it",
        ],
    },
    "sick": {
        "emojis": [
            "🤢", "🤮", "😷", "🤒", "🤕", "🥴", "😵", "🤧", "🥶", "🥵",
        ],
        "captions": [
            "Not feeling great",
            "Take care today",
            "Rest and recover",
            "Slow down and heal",
            "Body needs a break",
            "Easy day today",
            "Take it easy",
            "Recovery mode",
            "Be gentle with yourself",
            "Time to rest",
        ],
    },
    "focus": {
        "emojis": [
            "🤓", "🧐", "💻", "📈", "🎯", "🚀", "🧠", "🕹️", "⏳", "📊",
        ],
        "captions": [
            "Focus mode on",
            "Time to get things done",
            "Locked in",
            "Deep work time",
            "Stay sharp",
            "No distractions",
            "Get in the zone",
            "Productive day ahead",
            "Eyes on the goal",
            "Let’s build something",
        ],
    },
    "adventure": {
        "emojis": [
            "✈️", "🌍", "🌞", "🚀", "🗺️", "🎒", "🏝️", "🌄", "🌌", "🧭",
        ],
        "captions": [
            "Ready for adventure",
            "Explore something new",
            "Let’s go somewhere",
            "New horizons today",
            "Break the routine",
            "Adventure awaits",
            "Time to explore",
            "Go beyond",
            "Try something different",
            "See the world",
        ],
    },
    "love": {
        "emojis": [
            "❤️", "💖", "💘", "💞", "🥰", "😍", "😘", "😽", "💕", "❤️‍🔥",
        ],
        "captions": [
            "Love is in the air",
            "Feeling the love",
            "Heart full today",
            "Spread some love",
            "Warm and happy",
            "Sweet vibes",
            "Love mode on",
            "All about love",
            "Good feelings inside",
            "Share the love",
        ],
    },
}

# Caption translations per language. Only captions are translated; debug info remains English.
# Languages supported including Brazilian Portuguese variant: de, en, es, fr, id, it, nl, pt, pt-br
ENGLISH_CAPTIONS = {k: v["captions"] for k, v in MOOD_DATA.items()}

# Lazy-loaded translations: load per-language JSON files on first access and cache them.
_translations_cache = {"en": ENGLISH_CAPTIONS}

def _get_translations(language):
    """
    Return a mapping mood->list_of_captions for the given language.
    Loads `translations/<language>.json` on first use and caches it.
    Falls back to English captions if file is missing or invalid.
    """
    lang = str(language or "en").lower()

    # Allow only supported language codes to avoid path traversal attacks
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    if lang in _translations_cache:
        return _translations_cache[lang]

    translations_dir = os.path.join(os.path.dirname(__file__), "translations")
    filename = f"{lang}.json"
    path = os.path.join(translations_dir, filename)

    # Verify resolved path is inside translations_dir to prevent traversal
    try:
        translations_dir_real = os.path.realpath(translations_dir)
        path_real = os.path.realpath(path)
        if os.path.commonpath([translations_dir_real, path_real]) != translations_dir_real:
            logger.debug("EmojiMood: translation path outside translations dir: %s", path_real)
            _translations_cache[lang] = ENGLISH_CAPTIONS
            return ENGLISH_CAPTIONS
    except Exception:
        logger.exception("EmojiMood: error resolving translation paths for %s", lang)
        _translations_cache[lang] = ENGLISH_CAPTIONS
        return ENGLISH_CAPTIONS

    try:
        with open(path_real, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                _translations_cache[lang] = data
                return data
            else:
                logger.warning("EmojiMood: translation file %s did not contain a dict", path_real)
    except FileNotFoundError:
        logger.debug("EmojiMood: translation file not found: %s", path_real)
    except Exception:
        logger.exception("EmojiMood: failed to load translations for %s", lang)

    _translations_cache[lang] = ENGLISH_CAPTIONS
    return ENGLISH_CAPTIONS


class EmojiMood(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        # Determine selected mood from plugin settings.
        selected_mood_value = None
        if isinstance(settings, dict):
            selected_mood_value = settings.get("mood")
        if not selected_mood_value:
            selected_mood_value = "random"

        selected_mood_key = str(selected_mood_value).lower()

        # Determine the final mood key.
        # Resolve timezone once (used only for the "smart" selection)
        tz_name = device_config.get_config("timezone") or "UTC"
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone("UTC")

        if selected_mood_key == "random":
            mood_key = random.choice(list(MOOD_DATA.keys()))
        elif selected_mood_key == "smart":
            mood_key = _get_smart_mood(tz)["mood"]
        else:
            mood_key = selected_mood_key if selected_mood_key in MOOD_DATA else random.choice(list(MOOD_DATA.keys()))

        mood = MOOD_DATA[mood_key]
        emoji = random.choice(mood["emojis"])

        # Determine selected language (default 'en') and pick a translated caption list for the mood
        language = "en"
        if isinstance(settings, dict):
            language = str(settings.get("language") or "en").lower()

        translations = _get_translations(language)
        captions_for_mood = translations.get(mood_key, MOOD_DATA[mood_key]["captions"])
        caption = random.choice(captions_for_mood)

        # Show caption: strict true/false setting
        show_caption = True
        if isinstance(settings, dict):
            show_caption_value = str(settings.get("showCaption") or "true").lower()
            show_caption = show_caption_value == "true"

        template_params = {
            "emoji": emoji,
            "twemoji_url": _emoji_to_twemoji_url(emoji),
            "caption": caption,
            "plugin_settings": settings,
            "show_caption": show_caption,
        }

        image = self.render_image(
            dimensions, "emoji_mood.html", "emoji_mood.css", template_params
        )
        return image
