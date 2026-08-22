from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "Plumber Assistant API"
    DEBUG: bool = False

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "plumber_assistant"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    @property
    def DATABASE_URL(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"mysql+pymysql://{quote_plus(self.DB_USER)}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # The client's remote (GoDaddy) MySQL. The app itself never reads from it —
    # RAG search is far too slow over that link — but two standalone scripts use
    # it: import_items_from_remote.py pulls the catalog in, and sync_to_remote.py
    # pushes new orders/customers back out. Empty host disables both.
    REMOTE_DB_HOST: str = ""
    REMOTE_DB_PORT: int = 3306
    REMOTE_DB_NAME: str = ""
    REMOTE_DB_USER: str = ""
    REMOTE_DB_PASSWORD: str = ""

    # Provider selection: "openai" (production default) or "gemini" (local demo).
    LLM_PROVIDER: str = "openai"      # who phrases replies
    SPEECH_PROVIDER: str = "openai"   # who does speech-to-text

    OPENAI_API_KEY: str = ""
    OPENAI_TRANSCRIPTION_MODEL: str = "whisper-1"
    OPENAI_TTS_MODEL: str = "gpt-4o-mini-tts"
    OPENAI_TTS_VOICE: str = "alloy"

    # Gemini (used when *_PROVIDER=gemini). Key lives only in .env.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    # Wording replies is a much smaller job than understanding speech, so it gets
    # its own model. Measured on the same prompt: gemini-flash-lite-latest 690 ms
    # against gemini-flash-latest 1,698 ms. Empty falls back to GEMINI_MODEL, and
    # transcription is deliberately left on GEMINI_MODEL either way.
    GEMINI_TEXT_MODEL: str = "gemini-flash-lite-latest"

    # Do not ask a model to reword a reply the code has already composed.
    #
    # A search reply is a numbered product list built in services/response.py,
    # and the model was being handed it purely to say the same thing again. That
    # call measured 4.1 s, which was most of the wait for every single search.
    # The numbers in the list have to match what "add item 2" resolves to, so
    # composing them in code was always the safer design; the model was adding
    # latency and a chance of drift, not information.
    #
    # False restores the old behaviour, so this is the one-line revert.
    SMART_REPLIES: bool = True

    # Transcription usually answers in 3 to 5 seconds, but about one call in five
    # stalls for 13 to 21 with no relation to the length of the clip. Nobody
    # waits 21 seconds, so give up and ask them to repeat instead: a fast "say
    # that again" beats a very slow answer.
    TRANSCRIBE_TIMEOUT_SECONDS: int = 12

    # Text-to-speech. A separate model: the chat models cannot return audio.
    # Voices are Google's prebuilt set (Kore, Puck, Charon, Aoede, Fenrir...).
    # Set GEMINI_TTS_MODEL empty to skip server-side speech entirely and let the
    # browser speak the reply with its own built-in voice.
    GEMINI_TTS_MODEL: str = "gemini-2.5-flash-preview-tts"
    GEMINI_TTS_VOICE: str = "Kore"

    # Static ffmpeg (used to transcode browser WebM → WAV for Gemini speech-to-text).
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    # Endpoint of the client's image API (the DB stores only filenames). Filenames
    # are appended as "?folder=jjimages&image=<filename>", e.g.
    # "https://jj.fordev.fun/api/api.php". Empty → the UI shows a category-icon
    # fallback. Set this (no rebuild needed) to light up real photos.
    IMAGE_BASE_URL: str = ""

    # Public origin of THIS API (e.g. "https://dev.agent.fordev.fun"). When set,
    # product image_url is served as a stable "<PUBLIC_BASE_URL>/api/v1/media/{id}"
    # link that redirects to the real photo — so the URL never changes when the
    # upstream host/folder layout does. Empty → serialize the resolved photo URL
    # directly (the media endpoint still works, it just isn't the advertised URL).
    PUBLIC_BASE_URL: str = ""

    #: Where the website is, as a resident's phone would reach it. A parking QR
    #: points at a page on it, so scanning with any camera lands somewhere
    #: useful rather than showing hex to somebody at a barrier. Deliberately not
    #: PUBLIC_BASE_URL, which is the API's origin and is empty here.
    SITE_BASE_URL: str = "https://serviceagent.fordev.fun"

    SMTP_HOST: str = "smtp-relay.brevo.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    AI_ORDER_EMAIL: str = ""

    # ── search performance ───────────────────────────────────────────────────
    # The catalog's embeddings are held in memory (app/services/catalog_index.py)
    # so a product search doesn't re-read all ~25k rows out of MySQL every time.
    # Set RAG_USE_INDEX=false to fall straight back to the original database scan
    # — correct, just slow. It's the one-line revert if the index ever misbehaves.
    RAG_USE_INDEX: bool = True

    # Load the embedding model and build the index when the service boots, rather
    # than making the first shopper of the day wait for both. Runs in a background
    # thread, so the API starts answering immediately either way.
    WARMUP_ON_STARTUP: bool = True

    # Guards POST /api/v1/admin/reindex, which rebuilds the index after the
    # catalog changes. Empty (the default) disables that endpoint entirely.
    ADMIN_TOKEN: str = ""

    # Safety valve: refuse to build an index larger than this many rows and keep
    # using the database path instead, rather than exhausting a small instance.
    INDEX_MAX_ROWS: int = 200_000

    # ── payments ─────────────────────────────────────────────────────────────
    # Master switch. False makes /payments/* refuse and puts orders straight into
    # "confirmed" the way they were before payment existed, so it is the one-line
    # revert if a provider misbehaves.
    PAYMENTS_ENABLED: bool = True

    # Stripe hosted Checkout: cards, Apple Pay and Google Pay in one integration.
    # The webhook secret is NOT the API key; it comes from the endpoint's own page
    # in the Stripe dashboard, or from `stripe listen` during local testing.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # PayPal Orders v2. Base URL decides sandbox vs live, so switching to
    # production is a URL change plus live credentials, nothing in the code.
    # PAYPAL_WEBHOOK_ID comes from the webhook you create in their dashboard and
    # is required to verify deliveries.
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_SECRET: str = ""
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    PAYPAL_WEBHOOK_ID: str = ""

    PAYMENT_CURRENCY: str = "USD"

    # Cash on delivery. Independent of PAYMENTS_ENABLED: a shop can take cash
    # whether or not it can take cards, and turning the card providers off must
    # not silently turn every order into an unpaid one.
    #
    # False makes the checkout hide cash and the order endpoint refuse it, so
    # this is the one-line revert if the client decides against it.
    COD_ENABLED: bool = True

    # ── the diary ────────────────────────────────────────────────────────────
    # Which calendar to book against: "stub" (invented slots, no account and no
    # cost, labelled as examples in the interface) or "calendly" (the firm's own
    # diary). Same arrangement as the grocery system's search provider, so the
    # whole application can be built and shown before anybody buys a plan.
    # "local" holds the diary in our own database, which is the default and is
    # genuinely functional. "calendly" once the client sends their details.
    # "stub" invents slots and reserves nothing, and is for demonstrations only.
    CALENDAR_PROVIDER: str = "local"

    # The working day. A job has to finish inside it, so the last start depends
    # on how long the service takes rather than being a fixed time.
    BOOKING_OPEN_HOUR: int = 8
    BOOKING_CLOSE_HOUR: int = 17
    BOOKING_WEEKENDS: bool = False
    # How far apart offered slots are. An hour keeps the list readable.
    BOOKING_SLOT_STEP_MINUTES: int = 60
    # Nothing sooner than this, so we never offer a time nobody could reach.
    BOOKING_LEAD_HOURS: int = 3

    # ── accounts ─────────────────────────────────────────────────────────────
    # How long a signed-in session lasts. Long enough that a customer is not
    # asked again between booking a visit and the visit happening.
    SESSION_DAYS: int = 30

    # How providers are ordered when several offer the same service.
    # "soonest"  the first who can attend, then the cheapest of those
    # "price"    cheapest first
    # "distance" nearest first (needs a customer location)
    # "rating"   best rated first (needs ratings, which do not exist yet)
    #
    # A setting rather than a hard-coded sort, because it is a business rule and
    # the client may want to change it without a deployment.
    PROVIDER_RANKING: str = "soonest"

    CALENDLY_TOKEN: str = ""
    # One Calendly event type per service is what makes the durations right, so
    # a tap washer does not book the same hour as a new boiler. As
    # "service_id:event_type_uri", comma separated. Anything not listed falls
    # back to the default, which books but is wrong about length.
    CALENDLY_EVENT_TYPES: str = ""
    CALENDLY_DEFAULT_EVENT_TYPE: str = ""
    # Calendly signs its webhooks. Without this the endpoint would take a
    # cancellation from anybody who found the address.
    CALENDLY_WEBHOOK_SECRET: str = ""

    def calendly_event_types(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for pair in (self.CALENDLY_EVENT_TYPES or "").split(","):
            if ":" in pair:
                service_id, uri = pair.split(":", 1)
                out[service_id.strip()] = uri.strip()
        return out

    # How long a slot is held while the customer finishes the conversation.
    # Long enough to type an address, short enough that an abandoned chat does
    # not keep Tuesday morning to itself all afternoon.
    BOOKING_HOLD_MINUTES: int = 10

    # How far ahead the diary is offered.
    BOOKING_DAYS_AHEAD: int = 14


    # `items.store_id` and `items.module_id` are NOT NULL with no default, so a
    # created row has to supply both. An adopted product belongs to none of the
    # client's stores (his are 41, 42 and 43), so 0 marks it as ours rather than
    # misattributing it to one of his. module_id matches the value every one of
    # his 25,631 rows carries, so the item behaves like any other grocery line.
    ADOPTED_ITEM_STORE_ID: int = 0
    ADOPTED_ITEM_MODULE_ID: int = 9

    # How long to wait for adoptions to stop arriving before rebuilding the
    # index. A rebuild is a full 15 to 26 second pass over the whole catalog, so
    # doing one per adopted item would be wasteful. 0 rebuilds immediately.
    REINDEX_DEBOUNCE_SECONDS: int = 20

    SHOP_NAME: str = "AI Order"

    # Sales tax applied to the cart subtotal, as a fraction (0.08 = 8%).
    # Configurable in .env so the rate can change without a rebuild.
    TAX_RATE: float = 0.08

    FRONTEND_URL: str = "https://d2cvowfviwj76s.cloudfront.net"


settings = Settings()
