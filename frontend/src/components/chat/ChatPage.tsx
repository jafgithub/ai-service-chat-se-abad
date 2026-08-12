"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChatMessage } from "./ChatMessage";
import { ProductCard } from "./ProductCard";
import { CartDrawer } from "./CartDrawer";
import { CustomerInfoForm, type DeliverySlot } from "./CustomerInfoForm";
import { OrderConfirmation } from "./OrderConfirmation";
import { SourcedPanel } from "./SourcedPanel";
import { VendorProductModal } from "./VendorProductModal";
import { StoreBrowserModal } from "./StoreBrowserModal";
import { VisitingStoreBar } from "./VisitingStoreBar";

import { useCart } from "@/hooks/useCart";
import { useGeolocation } from "@/hooks/useGeolocation";
import { getSessionId, resetSessionId } from "@/lib/session";
import { clearPendingOrder, readPendingOrder, rememberPendingOrder } from "@/lib/pendingOrder";
import { chatApi, ordersApi, paymentsApi, shoppingApi, voiceApi, ApiError } from "@/lib/api";
import type { ProductResult, CustomerIn, PlaceOrderResponse, ExternalProduct, PaymentMethod } from "@/lib/api";
import { BRAND_NAME, PRODUCT_CATEGORIES } from "@/constants";
import type { ChatMessage as ChatMessageType } from "@/types";
import { cn } from "@/lib/utils";

/** Whether to look outside our own list. Never, here: a booking is with this
 *  firm or it is nothing, and the backend serves no such endpoint. */
const OFF_CATALOGUE_SEARCH = false;

interface ChatPageProps {
  scope?: string;
  onBack: () => void;
  /**
   * Show the retailer's own page inside the product popup, instead of drawing
   * it from the detail we hold. Set only by /v1/chat. Everything else on the
   * page behaves identically either way.
   */
  browserView?: boolean;
}

type ChatStep = "chat" | "checkout" | "confirmed";

// ── Voice turn tuning (all milliseconds) ─────────────────────────────────────
// The microphone stays open for the whole conversation; these decide when one
// spoken turn has ended so the recording can be sent off for an answer.
const SILENCE_AFTER_SPEECH = 1200; // they stopped talking: take the turn
const SILENCE_BEFORE_SPEECH = 6000; // they never started: listen again, no API call
const MAX_UTTERANCE = 15000;       // hard stop, so a stuck stream cannot record forever
const MIN_CLIP_BYTES = 1200;       // anything smaller carries no speech worth sending
const POLL_INTERVAL = 100;         // setInterval, not requestAnimationFrame, which
                                   // stops firing when the tab is in the background

// How loud counts as silence is a property of the room, not a number we can pick
// in advance. It was fixed at 10, and in any room whose background sits above
// that the level never drops below the bar, so the turn never ends and the
// recording runs to MAX_UTTERANCE. That is exactly what was happening: real
// turns were arriving at 14.6 seconds against a 15 second cap.
//
// So listen to the room first and set the bar above whatever it is doing.
const CALIBRATION_MS = 500;        // how long to listen before judging anything
const NOISE_MARGIN = 1.6;          // speech has to beat the room by this much
const NOISE_HEADROOM = 6;          // plus a fixed margin, for a very quiet room
const MIN_SILENCE_LEVEL = 10;      // never go below the original fixed value

// ── How many results to put on screen at once ────────────────────────────────
// The grid used to render every match. A search for "milk" returns 412 products
// and "chicken" returns 634, so the browser was mounting 634 cards and firing
// 634 image requests for a reply whose text said "here are the best 5". Nothing
// is hidden: "Show more" reveals the next page, and the true total is stated.
const PAGE_SIZE = 24;

// ── Sorting ──────────────────────────────────────────────────────────────────
// Relevance is the catalog's own similarity score, which is the order the
// search already returns, so it costs nothing to keep as the default. Price
// ascending is the other one the client asked for.
const SORT_OPTIONS = [
  { id: "relevance", label: "Relevance" },
  { id: "price_asc", label: "Lowest price" },
] as const;

type SortBy = (typeof SORT_OPTIONS)[number]["id"];

// ── When to look outside our own catalog ─────────────────────────────────────
// The client's rule: our own catalog first, and only when it comes back with
// nothing at all do we spend a paid search.
//
// Worth knowing how rarely that fires. The catalog keeps anything scoring above
// 0.35 against 25,631 products, so almost any phrase matches something:
// "wedding dress" returns 67 products and "titanium bicycle frame" returns one.
// Genuine empties do happen ("mortgage refinancing" returns none) but they are
// the exception, which is exactly why the manual button below exists. That
// button is the main way a shopper reaches the extended stores, and the
// automatic path is the safety net.

function TypingIndicator() {
  return (
    <div className="mb-4 flex gap-3" role="status" aria-label="Assistant is replying">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-brand-50 text-base">
        📅
      </div>
      <div className="flex items-center gap-1.5 rounded-card rounded-tl-sm border border-line bg-surface px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="animate-rise h-1.5 w-1.5 rounded-full bg-ink-faint"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}

function getCategoryInfo(scope: string | undefined) {
  if (!scope) return null;
  return PRODUCT_CATEGORIES.find((c) => c.chatScope === scope) ?? null;
}

export function ChatPage({ scope, onBack, browserView = false }: ChatPageProps) {
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [products, setProducts] = useState<ProductResult[]>([]);
  // How many of `products` are on screen. Reset by the effect below whenever a
  // new set of results arrives, so page 3 of "milk" never carries into "bread".
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  // What the results are answering, so the panel can say so.
  const [resultsFor, setResultsFor] = useState("");
  // The eleven stores, browsable in a frame. Only /v1/chat offers this.
  const [browsingStores, setBrowsingStores] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("relevance");
  // How many matched in total. `products` holds only the best 100 the server
  // sends, so this is what the header reports.
  const [totalMatches, setTotalMatches] = useState(0);
  /* Which set of results the pane is showing. Two horizontal rails were tried
     first and were poor: sideways scanning is slower than a grid, awkward with
     a mouse, and stacking two of them wasted the desktop's vertical space. A
     toggle gives each set the whole pane and a proper grid, and the extended
     results are one click away instead of below a page of cards. */
  const [resultsTab, setResultsTab] = useState<"ours" | "others">("ours");
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [step, setStep] = useState<ChatStep>("chat");
  const [cartOpen, setCartOpen] = useState(false);
  const [placingOrder, setPlacingOrder] = useState(false);
  // A ref, not the state above: state updates are batched, so a second submit
  // can arrive before `placingOrder` has flipped. Money is involved, so the
  // guard has to be synchronous.
  const placingOrderRef = useRef(false);
  const [confirmedOrder, setConfirmedOrder] = useState<PlaceOrderResponse | null>(null);
  // Set when we come back from a provider. The order number is in the URL, so it
  // is known even in the rare case where the order itself cannot be fetched.
  const [paidOrderId, setPaidOrderId] = useState<number | null>(null);
  // True while the webhook has not landed yet, so the screen can say "confirming"
  // rather than claim an order is placed before the server agrees.
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
  // Set by the return-trip effect, consumed by init(). See both for why.
  const cancelledNoticeRef = useRef<string | null>(null);


  // Products we do not stock, found elsewhere. Kept apart from `products` so
  // they are never mistaken for our own inventory.
  const [sourced, setSourced] = useState<ExternalProduct[]>([]);
  const [sourcedQuery, setSourcedQuery] = useState("");
  const [sourcedLoading, setSourcedLoading] = useState(false);
  const [adoptingId, setAdoptingId] = useState<string | null>(null);
  const [adoptedIds, setAdoptedIds] = useState<string[]>([]);
  /* Whether the configured provider invents its results. Fetched once: the
     panel has to say so, and the "Request this" button has to be withheld,
     because a fabricated product that reaches the catalog is orderable. One
     did ("Organic Banks, 100g", $12.99). */
  const [shoppingSample, setShoppingSample] = useState(false);
  /* The product a shopper left to look at on a retailer's own site. Our Add to
     Cart cannot be drawn on top of their page (they forbid being embedded), so
     it waits here instead and is one click away when they switch back. */
  const [visitingProduct, setVisitingProduct] = useState<ExternalProduct | null>(null);
  /* The vendor product whose page is open in our popup. */
  const [openProduct, setOpenProduct] = useState<ExternalProduct | null>(null);
  useEffect(() => {
    let dropped = false;
    shoppingApi
      .status()
      .then((st) => { if (!dropped) setShoppingSample(Boolean(st.sample)); })
      .catch(() => {});
    return () => { dropped = true; };
  }, []);

  // Voice loop plumbing
  const voiceActiveRef = useRef(false);   // continuous mode on/off (read inside async callbacks)
  const voiceTurnRef = useRef<() => void>(() => {});   // latest turn fn, so the loop recurses via a ref
  const streamRef = useRef<MediaStream | null>(null);          // held open for the whole conversation
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);      // one per spoken turn
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const cart = useCart(sessionId);
  const geo = useGeolocation();
  const category = getCategoryInfo(scope);

  const STORAGE_KEY = "chat_messages";
  const PRODUCTS_KEY = "chat_products";

  const addMessage = useCallback((role: "user" | "assistant", content: string) => {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role, content, timestamp: new Date() }]);
  }, []);

  /** Look outside our catalog, but only when our own results are weak.
   *
   * "No results at all" turns out to be the wrong test. The search keeps
   * anything scoring above 0.35, and against a 25,631 line grocery catalog that
   * returns something for almost any query: "wedding dress" comes back with 63
   * products. So weakness is judged two ways, and either is enough:
   *
   *   - barely anything matched at all, or
   *   - the single best match is poor
   *
   * Measured for calibration: "milk" tops out at 0.494 and "chicken breast" at
   * 0.61, both genuine. "titanium bicycle frame" returns one row at 0.369.
   *
   * Off-catalog results cost a third-party call, so this deliberately does not
   * fire on every message. */
  const findElsewhere = useCallback(async (
    query: string,
    own: ProductResult[],
    intent?: string | null,
  ) => {
    /* Only a genuine product search. Every other kind of message returns no
       products, which looks exactly like "we stock nothing like this" and used
       to send "add item 2 to cart", "checkout" and "show me my cart" off to the
       paid search. Measured against the live server, cart messages are most of
       a session, so this was the difference between a search allowance lasting
       a month and lasting a week. */
    if (intent && intent !== "search") {
      setSourced([]);
      return;
    }

    if (!query.trim() || own.length > 0) {
      // We stock something. Show ours, spend nothing.
      setSourced([]);
      return;
    }
    // This system has no off-catalogue search: there is no equivalent of buying
    // a jar from another shop when what you need is somebody to attend. The
    // calls are left in place rather than torn out, because the shop and this
    // share a component, and gated here so nothing is requested that the
    // backend does not serve.
    if (!OFF_CATALOGUE_SEARCH) {
      setSourced([]);
      return;
    }
    setSourcedLoading(true);
    setSourcedQuery(query);
    try {
      const found = await shoppingApi.search(query);
      setSourced(found);
      /* Our own catalog found nothing, so "Our store" is an empty screen. If
         other stores turned something up, that is the only useful thing on the
         page and the shopper should not have to discover a tab to see it. */
      if (found.length > 0) setResultsTab("others");
    } catch {
      // Nothing to show is a fine outcome here: the panel simply stays hidden
      // rather than putting an error in front of the shopper.
      setSourced([]);
    } finally {
      setSourcedLoading(false);
    }
  }, []);

  /** The "search our extended stores" button.
   *
   * Deliberately bypasses the automatic rule. Our catalog matches something for
   * almost any phrase, so the automatic path fires rarely; this is how a shopper
   * who can see our results and still is not satisfied reaches the wider search.
   * It is a press, so spending a search here is the shopper's own choice. */
  const searchExtendedStores = useCallback(async (query: string) => {
    if (!OFF_CATALOGUE_SEARCH) return;
    const q = query.trim();
    if (!q || sourcedLoading) return;
    setSourcedLoading(true);
    setSourcedQuery(q);
    // Switch to that view before the request finishes, so the shopper sees the
    // loading state rather than pressing a button and watching nothing happen.
    setResultsTab("others");
    try {
      setSourced(await shoppingApi.search(q));
    } catch {
      setSourced([]);
      addMessage(
        "assistant",
        "I could not reach the extended stores just now. Please try again shortly.",
      );
    } finally {
      setSourcedLoading(false);
    }
  }, [sourcedLoading, addMessage]);

  /** Bring an off-catalog product into the catalog and the cart. */
  const adoptProduct = useCallback(async (product: ExternalProduct) => {
    if (adoptingId) return;
    setAdoptingId(product.source_id);
    try {
      const res = await shoppingApi.adopt(
        // Whatever the caller chose travels with it: the popup sends the store,
        // its price and its page, so the product is stored as the shopper saw
        // it rather than as the search first quoted it.
        sessionId || getSessionId(), product, sourcedQuery,
      );
      cart.applyServerCart(res.cart);
      setAdoptedIds((prev) => [...prev, product.source_id]);
      addMessage(
        "assistant",
        `Added **${res.product.name}** to your cart. We do not stock this one, so we will source it for you and confirm the price before you pay.`
      );
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Could not add that item.";
      addMessage("assistant", `❌ ${msg}`);
    } finally {
      setAdoptingId(null);
    }
  }, [adoptingId, sessionId, sourcedQuery, cart, addMessage]);

  // ── Continuous voice ───────────────────────────────────────────
  // The whole turn runs on the server: it hears the clip, works out what was
  // meant, searches or updates the cart, and sends back the spoken reply. The
  // browser only records and plays.
  //
  // Speak the assistant's reply. Plays the audio the server generated; if the
  // provider is unavailable it returns no audio and the browser's own voice
  // stands in, so a speech outage never costs the reply itself. Resolves when
  // playback ends so the loop can take the next turn.
  const speak = useCallback((dataUrl: string, text: string) => new Promise<void>((resolve) => {
    setIsSpeaking(true);
    const done = () => { setIsSpeaking(false); resolve(); };

    if (dataUrl) {
      const audio = new Audio(dataUrl);
      audioRef.current = audio;
      audio.onended = done;
      audio.onerror = done;
      audio.play().catch(done);
      return;
    }

    const synth = typeof window !== "undefined" ? window.speechSynthesis : null;
    if (!synth || !text.trim()) { done(); return; }
    synth.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.onend = done;
    utter.onerror = done;
    synth.speak(utter);
  }), []);

  const closeMic = useCallback(() => {
    try { recorderRef.current?.stop(); } catch { /* already stopped */ }
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (audioCtxRef.current?.state !== "closed") audioCtxRef.current?.close();
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, []);

  const stopVoice = useCallback(() => {
    voiceActiveRef.current = false;
    setIsListening(false);
    setIsSpeaking(false);
    closeMic();
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
  }, [closeMic]);

  // Open the microphone once per conversation rather than once per turn: asking
  // for it every turn re-triggers the permission plumbing and blinks the browser's
  // recording indicator between every sentence.
  const openMic = useCallback(async (): Promise<boolean> => {
    if (streamRef.current) return true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      if (ctx.state === "suspended") await ctx.resume();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      streamRef.current = stream;
      audioCtxRef.current = ctx;
      analyserRef.current = analyser;
      return true;
    } catch {
      return false;    // permission refused, or no microphone
    }
  }, []);

  // Record one spoken turn. Resolves with the clip, or null when nothing was said
  // (so the caller can listen again without spending an API call on silence).
  const recordUtterance = useCallback((): Promise<Blob | null> => new Promise((resolve) => {
    const stream = streamRef.current;
    const analyser = analyserRef.current;
    if (!stream || !analyser) { resolve(null); return; }

    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    const chunks: Blob[] = [];
    const bins = new Uint8Array(analyser.frequencyBinCount);

    let heardSpeech = false;
    let quietSince = Date.now();
    const startedAt = Date.now();
    const roomSamples: number[] = [];
    let threshold = MIN_SILENCE_LEVEL;

    const finish = () => { if (recorder.state === "recording") recorder.stop(); };
    const hardStop = setTimeout(finish, MAX_UTTERANCE);
    const poll = setInterval(() => {
      if (recorder.state !== "recording") return;
      analyser.getByteFrequencyData(bins);
      const level = bins.reduce((sum, v) => sum + v, 0) / bins.length;
      const now = Date.now();

      if (now - startedAt < CALIBRATION_MS) {
        // Still listening to the room. Nothing counts as speech or as silence
        // yet, so hold the clock still.
        roomSamples.push(level);
        quietSince = now;
        return;
      }

      if (roomSamples.length > 0) {
        // The quietest moment, not the average: if they started talking during
        // calibration the average is their voice, and the bar ends up so high
        // that nothing ever counts as speech.
        const floor = Math.min(...roomSamples);
        threshold = Math.max(MIN_SILENCE_LEVEL, floor * NOISE_MARGIN + NOISE_HEADROOM);
        roomSamples.length = 0;
      }

      if (level > threshold) { heardSpeech = true; quietSince = now; }
      // Two different waits: a short one once they have spoken, so the reply comes
      // back quickly, and a long one when they never started, so a pause to think
      // is not mistaken for the end of a turn.
      if (now - quietSince > (heardSpeech ? SILENCE_AFTER_SPEECH : SILENCE_BEFORE_SPEECH)) finish();
    }, POLL_INTERVAL);

    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
    recorder.onstop = () => {
      clearTimeout(hardStop);
      clearInterval(poll);
      recorderRef.current = null;
      setIsListening(false);
      const clip = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      resolve(heardSpeech && clip.size >= MIN_CLIP_BYTES ? clip : null);
    };

    setIsListening(true);
    recorder.start();
  }), []);

  // One turn: record → POST the audio to /voice → play the spoken reply → loop.
  // A single request covers speech-to-text, intent, search or cart and the reply,
  // so what the assistant heard and what it answered can never disagree.
  const voiceTurn = useCallback(async () => {
    if (!voiceActiveRef.current) return;

    const clip = await recordUtterance();
    if (!voiceActiveRef.current) return;
    if (!clip) {                                       // silence: listen again, no API call
      setTimeout(() => voiceTurnRef.current(), 300);
      return;
    }

    setIsLoading(true);
    let goCheckout = false;
    try {
      const res = await voiceApi.send(clip, {
        sessionId: sessionId || getSessionId(),
        categoryFilter: scope ?? undefined,
        latitude: geo.position?.latitude,
        longitude: geo.position?.longitude,
      });
      setIsLoading(false);
      if (!voiceActiveRef.current) return;

      const heard = (res.transcript ?? "").trim();
      if (!heard) {                                    // audio arrived but held no words
        setTimeout(() => voiceTurnRef.current(), 300);
        return;
      }
      addMessage("user", heard);
      addMessage("assistant", res.reply);
      if (res.services.length > 0) {
        setProducts(res.services);
        setTotalMatches(res.total_services ?? res.services.length);
        setVisibleCount(PAGE_SIZE);
        setResultsFor(heard);
        setResultsTab("ours");
      } else if (res.action === null) {
        setProducts([]);
        setTotalMatches(0);
        setVisibleCount(PAGE_SIZE);
        setResultsFor(heard);
      }
      cart.applyServerCart(res.cart);
      void findElsewhere(heard, res.services, res.intent);
      goCheckout = res.action?.type === "checkout";
      // Speak the short version: long product lists are shown, not read out.
      await speak(res.audio ?? "", res.speech || res.reply);
    } catch {
      setIsLoading(false);
      addMessage("assistant", "Sorry, I couldn't process that. Please try again.");
    }

    if (goCheckout) { setStep("checkout"); stopVoice(); return; }
    if (voiceActiveRef.current) voiceTurnRef.current();      // keep the conversation going
  }, [recordUtterance, speak, stopVoice, sessionId, scope, geo.position, addMessage, cart, findElsewhere]);

  // Keep the ref pointed at the freshest turn fn so the loop always recurses correctly.
  useEffect(() => { voiceTurnRef.current = voiceTurn; }, [voiceTurn]);

  const toggleVoice = useCallback(async () => {
    if (typeof window === "undefined") return;
    if (voiceActiveRef.current) { stopVoice(); return; }
    // Recording works in every current browser, unlike the speech recognition
    // this replaced, which only ever ran in Chrome.
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      alert("This browser cannot record audio. Please type your request instead.");
      return;
    }
    if (!(await openMic())) {
      alert("I could not reach your microphone. Check the site's microphone permission, or type your request instead.");
      return;
    }
    voiceActiveRef.current = true;
    voiceTurnRef.current();
  }, [stopVoice, openMic]);

  useEffect(() => {
    async function init() {
      setSessionId(getSessionId());
      await geo.requestLocation();

      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          const parsed = JSON.parse(saved) as ChatMessageType[];
          if (parsed.length > 0) {
            setMessages(parsed.map((m) => ({ ...m, timestamp: new Date(m.timestamp) })));
            const savedProducts = localStorage.getItem(PRODUCTS_KEY);
            if (savedProducts) setProducts(JSON.parse(savedProducts));
            inputRef.current?.focus();
            return;
          }
        } catch {
          localStorage.removeItem(STORAGE_KEY);
          localStorage.removeItem(PRODUCTS_KEY);
        }
      }

      const greeting = scope
        ? `Hi! 👋 I'm here to help you with **${scope}**. What are you looking for today?`
        : "Hi! 👋 I'm your booking assistant. What do you need?";
      setMessages([{ id: crypto.randomUUID(), role: "assistant", content: greeting, timestamp: new Date() }]);
      inputRef.current?.focus();
    }
    init().then(() => {
      // A cancelled payment, if there was one. Appended after init has settled
      // so it survives the setMessages that seeds the conversation.
      const notice = cancelledNoticeRef.current;
      if (notice) {
        cancelledNoticeRef.current = null;
        addMessage("assistant", notice);
      }
    });
    // Stop any voice/audio when leaving the page.
    return () => stopVoice();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Coming back from Stripe or PayPal.
   *
   * The provider sends the shopper to `/chat?paid={order_id}` (or `?cancelled=`),
   * which used to be a dead end: nothing read the parameter, so someone who had
   * just paid landed on an empty chat page with their basket still full and no
   * sign the order existed. They could easily pay twice.
   *
   * The order id alone is not enough to fetch the order, deliberately, so the
   * idempotency key stashed before the redirect is what does the lookup.
   *
   * The setState calls below are flagged by react-hooks/set-state-in-effect,
   * and an effect really is the right place for them. The tidier alternative,
   * a lazy useState initializer, would run during the static prerender at build
   * time, where `window` does not exist and the query string is not knowable;
   * seeding state from it would be a hydration mismatch. Reading the URL after
   * mount is the "subscribe to an external system" case the rule allows for. */
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    const params = new URLSearchParams(window.location.search);
    const paid = params.get("paid");
    const cancelled = params.get("cancelled");
    if (!paid && !cancelled) return;

    // Take the parameter back out of the URL first, so a refresh or a shared
    // link does not replay a confirmation for an order that is long finished.
    const url = new URL(window.location.href);
    url.searchParams.delete("paid");
    url.searchParams.delete("cancelled");
    window.history.replaceState({}, "", url.toString());

    const pending = readPendingOrder();

    if (cancelled) {
      clearPendingOrder();
      // Handed to the init effect rather than appended here. init() finishes by
      // calling setMessages([greeting]), which replaces the whole list, so a
      // message added at this point would simply vanish a moment later.
      cancelledNoticeRef.current =
        "No problem, that payment was cancelled and you have not been charged. " +
        "Your booking is exactly as you left it whenever you want to try again.";
      return;
    }

    const orderId = Number(paid);
    if (!Number.isFinite(orderId) || orderId <= 0) return;

    setPaidOrderId(orderId);
    setStep("confirmed");
    // The basket belongs to the order now. The server already emptied it when
    // the order was created; this clears what the page is still holding.
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(PRODUCTS_KEY);

    // Without the key we can still name the order, just not itemise it.
    if (!pending || pending.orderId !== orderId) {
      clearPendingOrder();
      return;
    }

    let cancelledFetch = false;

    /* The redirect usually beats the webhook back, so the order is often still
       `pending` for a second or two after the shopper arrives. Poll briefly
       rather than either lying about the status or showing a spinner forever. */
    const poll = async (attempt = 0) => {
      if (cancelledFetch) return;
      try {
        const order = await ordersApi.byKey(pending.idempotencyKey);
        if (cancelledFetch) return;
        setConfirmedOrder(order);

        if (order.status === "pending" && attempt < 6) {
          setAwaitingConfirmation(true);
          setTimeout(() => poll(attempt + 1), 1500);
          return;
        }
        // Either confirmed, or the webhook is taking longer than we will wait.
        // The money is taken either way, so say so plainly and stop polling.
        setAwaitingConfirmation(order.status === "pending");
        clearPendingOrder();
      } catch {
        if (cancelledFetch) return;
        // A lookup failure must not hide the fact that they paid.
        clearPendingOrder();
      }
    };
    void poll();

    return () => { cancelledFetch = true; };
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  // Hydrate the server cart once we know the session id.
  useEffect(() => {
    if (sessionId) cart.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (messages.length > 0) localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    if (products.length > 0) localStorage.setItem(PRODUCTS_KEY, JSON.stringify(products));
  }, [products]);

  // ── Text chat ──────────────────────────────────────────────────
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;
    addMessage("user", text.trim());
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await chatApi.send({
        message: text.trim(),
        session_id: sessionId || getSessionId(),
        category_filter: scope ?? undefined,
        latitude: geo.position?.latitude,
        longitude: geo.position?.longitude,
      });
      addMessage("assistant", response.reply);
      // A search that found nothing has to clear the last one. Leaving the
      // previous results up meant the assistant said "I couldn't find anything
      // matching that" while the panel beside it still read "Results for milk"
      // and showed 24 cartons of milk. Only a *search* clears them: adding to
      // the cart also returns an empty product list, and that must leave the
      // results the shopper is picking from alone.
      if (response.services.length > 0) {
        setProducts(response.services);
        setTotalMatches(response.total_services ?? response.services.length);
        setVisibleCount(PAGE_SIZE);
        setResultsFor(text.trim());
        setResultsTab("ours");
      } else if (response.action === null) {
        setProducts([]);
        setTotalMatches(0);
        setVisibleCount(PAGE_SIZE);
        setResultsFor(text.trim());
      }
      cart.applyServerCart(response.cart);
      if (response.action?.type === "checkout") setStep("checkout");
      void findElsewhere(text.trim(), response.services, response.intent);
    } catch (err) {
      const msg = err instanceof ApiError
        ? `Sorry, something went wrong: ${err.detail}`
        : "Sorry, I couldn't connect to the server. Please try again.";
      addMessage("assistant", msg);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, scope, geo.position, sessionId, addMessage, cart, findElsewhere]);

  const handlePlaceOrder = useCallback(async (
    customer: CustomerIn,
    delivery: DeliverySlot,
    method: PaymentMethod,
  ) => {
    // Guard the whole handler, not just the button: React can batch state, and a
    // fast double tap or an Enter keypress would otherwise fire this twice.
    if (placingOrderRef.current) return;
    placingOrderRef.current = true;

    setPlacingOrder(true);

    // Generated once per attempt and reused on retry, so a duplicate request
    // returns the order that already exists instead of placing a second one.
    const idempotencyKey = crypto.randomUUID();

    try {
      const order = await ordersApi.place(
        sessionId
          ? {
              customer, session_id: sessionId, ...delivery,
              idempotency_key: idempotencyKey, payment_method: method,
            }
          : {
              customer,
              items: cart.items.map((i) => ({ product_id: i.product.id, quantity: i.quantity })),
              ...delivery,
              idempotency_key: idempotencyKey,
              payment_method: method,
            }
      );

      // An order that still needs paying is not finished. Send the shopper to
      // the provider; the order is only confirmed once their webhook says so.
      // Cash comes back already confirmed, so there is nothing to redirect to.
      if (order.status === "pending") {
        // The shopper's own choice, not providers[0]. That line always resolved
        // to Stripe, which meant PayPal was configured, paid for, and reachable
        // by nobody.
        const { url } = await paymentsApi.checkout(order.order_id, method);
        // Everything in React is about to be discarded by a full navigation.
        // The key is the one thing the return trip needs to identify what was
        // bought, so it goes somewhere that survives leaving the site.
        rememberPendingOrder(order.order_id, idempotencyKey);
        // The cart is deliberately NOT cleared here: if they abandon the
        // payment page they should come back to their basket intact.
        window.location.href = url;
        return;
      }

      setConfirmedOrder(order);
      cart.clearCart();
      localStorage.removeItem("chat_messages");
      localStorage.removeItem("chat_products");
      setStep("confirmed");
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Order failed. Please try again.";
      addMessage("assistant", `❌ ${msg}`);
      setStep("chat");
    } finally {
      placingOrderRef.current = false;
      setPlacingOrder(false);
    }
  }, [cart, sessionId, addMessage]);

  /** Start over with an empty conversation and an empty cart.
   *
   * A full reload rather than resetting state piecemeal: the session id keys the
   * server-side cart and the conversation memory, so a new one has to be issued
   * and every hook has to pick it up. Reloading is the only way to be sure the
   * previous order leaves no trace behind. */
  const startNewOrder = useCallback(() => {
    stopVoice();
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(PRODUCTS_KEY);
    clearPendingOrder();
    resetSessionId();
    window.location.href = "/chat";
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Deliberately not the three category names: the results pane already offers
     those as cards, and showing the same three chips twice on one screen made
     the page look like it had one idea. These prompt the thing the product is
     actually for, which is asking in your own words. */
  const quickReplies = scope
    ? ["What do you have?", "What are the prices?", "Show me everything"]
    : ["My kitchen sink is blocked", "My dog needs his vaccinations", "I need an end of tenancy clean"];
  const totalQty = cart.items.reduce((s, i) => s + i.quantity, 0);
  const micActive = isListening || isSpeaking;
  /* Sorting is applied before paging, so "lowest price" means the cheapest of
     all 634 matches rather than the cheapest of the 24 on screen. Sorting the
     visible slice instead would reorder a page and quietly hide the actual
     cheapest product, which is the opposite of what the control promises.

     A copy, because Array.sort mutates and `products` is state. */
  const sortedProducts = useMemo(() => {
    if (sortBy !== "price_asc") return products;   // relevance is the given order
    return [...products].sort((a, b) => a.price_per_unit - b.price_per_unit);
  }, [products, sortBy]);

  const visible = sortedProducts.slice(0, visibleCount);
  const hasMore = sortedProducts.length > visibleCount;

  // The same ordering for the extended-store panel, so one control governs
  // everything on screen rather than half of it.
  const sortedSourced = useMemo(() => {
    if (sortBy !== "price_asc") return sourced;
    return [...sourced].sort((a, b) => a.price - b.price);
  }, [sourced, sortBy]);
  // A search ran and matched nothing, as opposed to nobody having searched yet.
  // The two look identical in state and must not read the same on screen.
  const searchedAndFoundNothing = products.length === 0 && resultsFor !== "";
  // Whether the shopper can usefully press "search our extended stores": there
  // has to be something to search for.
  const canSearchExtended = resultsFor.trim().length > 0;

  /* Defined once, rendered twice: pinned under the conversation on a wide
     screen, and as a shared footer under both tabs on a phone. On a phone it
     has to sit outside the panes, or switching to Results would take the text
     box and the microphone away with it. */
  const composer = (
    <div className="flex-shrink-0 border-t border-line bg-surface px-4 py-3">
      <form
        onSubmit={(e) => { e.preventDefault(); sendMessage(inputValue); }}
        className="flex items-center gap-2"
      >
        <button
          type="button"
          onClick={toggleVoice}
          title={micActive ? "Stop voice conversation" : "Start voice conversation"}
          aria-label={micActive ? "Stop voice conversation" : "Start voice conversation"}
          aria-pressed={micActive}
          className={cn(
      "relative flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border transition-colors",
      micActive
        ? "border-danger bg-danger text-white"
        : "border-line bg-surface text-ink-muted hover:border-brand-300 hover:bg-brand-50 hover:text-brand-600"
          )}
        >
          {micActive && (
      <span className="absolute inset-0 animate-ping rounded-full bg-danger/30" aria-hidden />
          )}
          <svg className="relative h-5 w-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" />
      <path d="M19 10a7 7 0 0 1-14 0" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M12 19v3M9 22h6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
          </svg>
        </button>

        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={micActive ? (isSpeaking ? "Speaking…" : "Listening…") : "Describe the problem…"}
          disabled={isLoading || micActive}
          autoComplete="off"
          className="h-11 flex-1 rounded-control border border-line bg-surface-sunken px-4 text-sm text-ink placeholder-ink-faint transition-colors focus:border-brand-300 focus:bg-surface"
        />

        <button
          type="submit"
          disabled={!inputValue.trim() || isLoading}
          aria-label="Send"
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-brand-500 text-white transition-colors hover:bg-brand-600 disabled:bg-line-strong disabled:text-ink-faint"
        >
          {/* A plain arrow. The paper plane this replaced collapsed into
        something that read as a warning triangle at 20px. */}
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </form>

      <p className="mt-2 text-center text-xs text-ink-faint">
        {micActive
          ? "Voice conversation active. Tap the mic to stop."
          : geo.isRequesting
      ? "Finding your location…"
      : "Ask by voice or type. You will get an email confirmation."}
      </p>
    </div>
  );

  return (
    // h-dvh rather than h-screen: `vh` measures the viewport with the mobile
    // address bar hidden, which pushed the composer under the browser chrome.
    // Paired with viewportFit "cover" in layout.tsx, the padding keeps the
    // composer clear of the iOS home indicator.
    <div className="flex h-dvh flex-col overflow-hidden bg-surface-sunken pb-[env(safe-area-inset-bottom)]">

      {/* A plain white bar. This was a hot orange-to-rose gradient, which made
          the chrome the loudest thing on screen and left nothing to promote the
          one action that matters on each page. */}
      {/* The brand bar, restored at the client's request. It is the one coloured
          surface in the app: the cart drawer, the checkout sheet and the product
          buttons stay calm, which is what the redesign was actually fixing. A
          coloured header on its own was never the problem. */}
      <header className="z-30 flex-shrink-0 bg-gradient-to-r from-brand-500 to-rose-500">
        <div className="flex h-16 items-center gap-3 px-4">
          <button
            onClick={() => { stopVoice(); onBack(); }}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-white/90 transition-colors hover:bg-white/15 hover:text-white"
            aria-label="Back to home"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-white/20 text-lg">
            {category ? category.icon : "📅"}
          </div>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold leading-tight text-white">
              {BRAND_NAME}
              {category && <span className="font-normal text-white/75"> · {category.title}</span>}
            </p>
            <div className="mt-0.5 flex items-center gap-1.5">
              {/* White rather than green: a status colour on a coloured bar reads
                  as a warning light, and white keeps it legible. */}
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full bg-white",
                  micActive && "animate-pulse"
                )}
              />
              <span className="text-xs text-white/85">
                {micActive ? (isSpeaking ? "Speaking" : "Listening") : "Online"}
              </span>
            </div>
          </div>

          <button
            onClick={() => setCartOpen(true)}
            className={cn(
              "relative flex h-10 items-center gap-2 rounded-control px-3 text-sm font-semibold transition-colors",
              // Inverted when it has something in it, so the cart is still the
              // loudest thing on the bar rather than blending into the gradient.
              totalQty > 0
                ? "bg-white text-brand-600 hover:bg-white/90"
                : "text-white/90 hover:bg-white/15 hover:text-white"
            )}
            aria-label={totalQty > 0 ? `Open cart, ${totalQty} items` : "Open cart"}
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            {totalQty > 0 && <span className="tabular-nums">{totalQty}</span>}
          </button>
        </div>

      </header>

      <div className="flex flex-1 overflow-hidden">

        {/* ── Conversation ─────────────────────────────────────────────── */}
        <div className="flex w-full flex-shrink-0 flex-col border-r border-line bg-surface lg:w-[440px] xl:w-[500px]">

          {/* Phone only: results swipe sideways above the conversation, so both
              are on screen at once. A vertical grid here had to be capped by
              height, which sliced the second row through the middle; a sideways
              row simply runs off the edge, which is what invites the swipe. */}
          {(products.length > 0 || isLoading || canSearchExtended) && (
            <div className="flex-shrink-0 border-b border-line bg-surface-sunken lg:hidden">
              <div className="flex items-baseline justify-between px-4 pb-1.5 pt-2.5">
                <p className="text-xs font-medium text-ink">
                  {/* The true total, not how many were sent. The server caps the
                      list at 100; saying "100 matches" would understate a
                      1,118-match search. */}
                  {isLoading
                    ? "Searching…"
                    : `${totalMatches || products.length} match${(totalMatches || products.length) === 1 ? "" : "es"}`}
                </p>
                {/* Sorting on a phone is the same two choices, as a single
                    toggle: there is no room for a segmented control, and with
                    two options a toggle says everything a control would. */}
                {!isLoading && products.length > 1 && (
                  <button
                    onClick={() =>
                      setSortBy((v) => (v === "relevance" ? "price_asc" : "relevance"))
                    }
                    className="text-[11px] font-semibold text-brand-600"
                  >
                    {sortBy === "relevance" ? "Sort: Relevance" : "Sort: Lowest price"}
                  </button>
                )}
              </div>

              {/* overscroll-x-contain: without it, swiping past the last card
                  hands the gesture to the browser and navigates back. */}
              <div className="chat-scroll flex snap-x snap-mandatory gap-2.5 overflow-x-auto overscroll-x-contain px-4 pb-3">
                {isLoading
                  ? [1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="h-60 w-[150px] flex-shrink-0 animate-pulse rounded-card border border-line bg-surface"
                      />
                    ))
                  : (
                    <>
                      {visible.map((product) => {
                        const cartItem = cart.items.find((i) => i.product.id === product.id);
                        return (
                          <div key={product.id} className="w-[150px] flex-shrink-0 snap-start">
                            <ProductCard
                              product={product}
                              quantity={cartItem?.quantity ?? 0}
                              onAdd={cart.addItem}
                              onRemove={cart.removeItem}
                              onUpdateQty={cart.updateQty}
                              compact
                            />
                          </div>
                        );
                      })}

                      {/* Paging lives at the end of the row, so everything stays
                          reachable without a second screen to switch to. */}
                      {hasMore && (
                        <button
                          onClick={() => setVisibleCount((n) => n + PAGE_SIZE)}
                          className="flex w-[130px] flex-shrink-0 snap-start flex-col items-center justify-center gap-1 rounded-card border border-dashed border-line-strong bg-surface text-sm font-medium text-ink-muted"
                        >
                          <span className="text-lg" aria-hidden>+</span>
                          Show {Math.min(PAGE_SIZE, sortedProducts.length - visibleCount)} more
                        </button>
                      )}
                    </>
                  )}
              </div>

              {canSearchExtended && (
                <div className="px-4 pb-3">
                  <button
                    onClick={() => searchExtendedStores(resultsFor)}
                    disabled={sourcedLoading}
                    className="w-full rounded-control border border-dashed border-brand-300 bg-brand-50 px-3 py-2 text-[11px] font-semibold leading-snug text-brand-700 disabled:opacity-60"
                  >
                    {sourcedLoading
                      ? "Searching our extended stores…"
                      : "Still not finding it? Search our extended stores"}
                  </button>
                </div>
              )}

              {/* The extended results, on a phone. The desktop copy lives in the
                  results pane, which is hidden below `lg`, so without this the
                  button would fetch and the shopper would see nothing happen. */}
              {(sourced.length > 0 || sourcedLoading) && (
                <div className="max-h-[46vh] overflow-y-auto border-t border-line bg-surface px-4 pb-3">
                  <SourcedPanel
                    query={sourcedQuery}
                    products={sortedSourced}
                    loading={sourcedLoading}
                    adoptingId={adoptingId}
                    adoptedIds={adoptedIds}
                    onAdd={adoptProduct}
                    sample={shoppingSample}
                    onOpenProduct={setOpenProduct}
                  />
                </div>
              )}
            </div>
          )}

          <div className="chat-scroll flex flex-1 flex-col gap-1 overflow-y-auto px-4 py-5">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} large />
            ))}
            {isLoading && <TypingIndicator />}

            {messages.length === 1 && !isLoading && (
              <div className="ml-11 mt-3 flex flex-wrap gap-2">
                {quickReplies.map((r) => (
                  <button
                    key={r}
                    onClick={() => sendMessage(r)}
                    className="rounded-full border border-line bg-surface px-3.5 py-2 text-sm font-medium text-ink transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                  >
                    {r}
                  </button>
                ))}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {visitingProduct && (
            <VisitingStoreBar
              product={visitingProduct}
              busy={adoptingId === visitingProduct.source_id}
              added={adoptedIds.includes(visitingProduct.source_id)}
              onAdd={adoptProduct}
              onDismiss={() => setVisitingProduct(null)}
            />
          )}

          {composer}
        </div>

        {/* ── Results ──────────────────────────────────────────────────── */}
        <div className="hidden flex-1 flex-col overflow-hidden bg-surface-sunken lg:flex">

          <div className="flex flex-shrink-0 flex-col gap-3 border-b border-line bg-surface px-6 py-3">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">
                  {products.length > 0
                    ? resultsFor
                      ? `Results for “${resultsFor}”`
                      : "Results"
                    : searchedAndFoundNothing
                      ? `No matches for “${resultsFor}”`
                      : "Services"}
                </p>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {resultsTab === "others"
                    ? sourcedLoading
                      ? "Searching stores beyond ours…"
                      : `${sourced.length} from other stores`
                    : products.length > 0
                      ? totalMatches > products.length
                        ? `${totalMatches} matches, showing the best ${products.length}`
                        : `${products.length} match${products.length === 1 ? "" : "es"}`
                      : searchedAndFoundNothing
                        ? "We do not stock anything like that"
                        : "Ask the assistant, or pick a category to start"}
                </p>
              </div>

              {/* Browsing the named stores directly, rather than only the
                  products a search happened to surface. */}
              {browserView && canSearchExtended && (
                <button
                  onClick={() => setBrowsingStores(true)}
                  className="flex flex-shrink-0 items-center gap-1.5 rounded-control border border-line px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:bg-surface-hover"
                >
                  🏪 Browse stores
                </button>
              )}

              {/* Gated on whichever list is actually on screen. Keying it to our
                  own results meant the Other stores tab could never be sorted,
                  even with results sitting in it. */}
              {(resultsTab === "others" ? sourced.length : products.length) > 1 && (
                <div className="flex flex-shrink-0 items-center gap-1 rounded-control border border-line p-0.5">
                  {SORT_OPTIONS.map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => setSortBy(opt.id)}
                      aria-pressed={sortBy === opt.id}
                      className={cn(
                        "h-8 rounded-[0.5rem] px-3 text-xs font-medium transition-colors",
                        sortBy === opt.id
                          ? "bg-brand-50 text-brand-700"
                          : "text-ink-muted hover:bg-surface-hover"
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Both sets of results, one click apart. Our own stock is the
                default, so the client's products are never behind someone
                else's. */}
            {canSearchExtended && (
              <div className="flex items-center gap-2">
                <div className="flex flex-1 gap-1 rounded-control border border-line p-0.5">
                  <button
                    onClick={() => setResultsTab("ours")}
                    aria-pressed={resultsTab === "ours"}
                    className={cn(
                      "h-9 flex-1 rounded-[0.5rem] text-xs font-semibold transition-colors",
                      resultsTab === "ours"
                        ? "bg-brand-50 text-brand-700"
                        : "text-ink-muted hover:bg-surface-hover"
                    )}
                  >
                    Our store{totalMatches > 0 ? ` (${totalMatches})` : ""}
                  </button>
                  <button
                    onClick={() => {
                      // Fetch on first use; afterwards the toggle just switches.
                      if (sourced.length === 0 && !sourcedLoading) {
                        searchExtendedStores(resultsFor);
                      } else {
                        setResultsTab("others");
                      }
                    }}
                    aria-pressed={resultsTab === "others"}
                    className={cn(
                      "h-9 flex-1 rounded-[0.5rem] text-xs font-semibold transition-colors",
                      resultsTab === "others"
                        ? "bg-brand-50 text-brand-700"
                        : "text-ink-muted hover:bg-surface-hover"
                    )}
                  >
                    🌐 Other stores{sourced.length > 0 ? ` (${sourced.length})` : ""}
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="chat-scroll flex-1 overflow-y-auto px-5 py-5">
            {resultsTab === "others" ? (
              /* The whole pane, not a strip at the bottom of a long page. */
              <SourcedPanel
                query={sourcedQuery}
                products={sortedSourced}
                loading={sourcedLoading}
                adoptingId={adoptingId}
                adoptedIds={adoptedIds}
                onAdd={adoptProduct}
                sample={shoppingSample}
                onBackToOurs={() => setResultsTab("ours")}
                onOpenProduct={setOpenProduct}
              />
            ) : isLoading ? (
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-4">
                {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                  <div key={i} className="overflow-hidden rounded-card border border-line bg-surface">
                    <div className="h-32 w-full animate-pulse bg-surface-hover" />
                    <div className="space-y-2 p-3">
                      <div className="h-3 w-3/4 animate-pulse rounded bg-surface-hover" />
                      <div className="h-3 w-1/2 animate-pulse rounded bg-surface-hover" />
                      <div className="mt-2 h-10 w-full animate-pulse rounded-control bg-surface-hover" />
                    </div>
                  </div>
                ))}
              </div>
            ) : products.length > 0 ? (
              <>
                <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-4">
                  {visible.map((product) => {
                    const cartItem = cart.items.find((i) => i.product.id === product.id);
                    return (
                      <ProductCard
                        key={product.id}
                        product={product}
                        quantity={cartItem?.quantity ?? 0}
                        onAdd={cart.addItem}
                        onRemove={cart.removeItem}
                        onUpdateQty={cart.updateQty}
                      />
                    );
                  })}
                </div>

                {hasMore && (
                  <div className="mt-5 flex flex-col items-center gap-1.5">
                    <button
                      onClick={() => setVisibleCount((n) => n + PAGE_SIZE)}
                      className="h-11 rounded-control border border-line bg-surface px-6 text-sm font-medium text-ink transition-colors hover:bg-surface-hover"
                    >
                      Show {Math.min(PAGE_SIZE, sortedProducts.length - visibleCount)} more
                    </button>
                    <p className="text-xs text-ink-faint">
                      {sortedProducts.length - visibleCount} more to see
                    </p>
                  </div>
                )}
              </>
            ) : (
              /* The arrival state. This was a magnifying glass in the middle of
                 two thirds of an empty screen; now it is somewhere to start. */
              <div className={cn(
                "flex flex-col",
                sourced.length === 0 && !sourcedLoading ? "h-full justify-center" : "py-4"
              )}>
                <div className="mx-auto w-full max-w-2xl">
                  <h2 className="text-base font-semibold text-ink">
                    {searchedAndFoundNothing
                      ? `Nothing here matches “${resultsFor}”`
                      : "What do you need help with?"}
                  </h2>
                  <p className="mt-1 text-sm text-ink-muted">
                    {searchedAndFoundNothing
                      ? "Try different words, or start from a category."
                      : "Describe it in your own words, or start with a category."}
                  </p>

                  <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                    {PRODUCT_CATEGORIES.map((cat) => (
                      <button
                        key={cat.id}
                        onClick={() => sendMessage(`Show me ${cat.title}`)}
                        className="group flex flex-col items-start gap-2 rounded-card border border-line bg-surface p-4 text-left transition-shadow hover:shadow-card-hover"
                      >
                        <span className="flex h-11 w-11 items-center justify-center rounded-control bg-brand-50 text-2xl">
                          {cat.icon}
                        </span>
                        <span className="text-sm font-semibold text-ink">{cat.title}</span>
                        <span className="text-xs leading-relaxed text-ink-muted line-clamp-2">
                          {cat.description}
                        </span>
                      </button>
                    ))}
                  </div>

                  <div className="mt-6">
                    <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">
                      Or try
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {["Blocked drain", "Vet appointment", "Boiler service", "House clean", "Car service"].map((example) => (
                        <button
                          key={example}
                          onClick={() => sendMessage(example)}
                          className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-sm text-ink-muted transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

          </div>

          {!cart.isEmpty && (
            <div className="flex flex-shrink-0 items-center justify-between gap-4 border-t border-line bg-surface px-6 py-3">
              <div>
                <p className="text-xs text-ink-muted">
                  {totalQty} item{totalQty !== 1 ? "s" : ""} in your cart
                </p>
                <p className="text-lg font-bold leading-tight tabular-nums text-ink">
                  ${cart.total.toFixed(2)}
                </p>
              </div>
              <button
                onClick={() => setCartOpen(true)}
                className="h-11 rounded-control bg-brand-500 px-6 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
              >
                Review cart
              </button>
            </div>
          )}
        </div>

      </div>

      <CartDrawer
        isOpen={cartOpen}
        onClose={() => setCartOpen(false)}
        items={cart.items}
        subtotal={cart.subtotal}
        tax={cart.tax}
        total={cart.total}
        onUpdateQty={cart.updateQty}
        onRemove={cart.removeItem}
        onConfirmOrder={() => setStep("checkout")}
      />

      {browsingStores && (
        <StoreBrowserModal query={resultsFor} onClose={() => setBrowsingStores(false)} />
      )}

      {openProduct && (
        <VendorProductModal
          product={openProduct}
          browserView={browserView}
          sample={shoppingSample}
          adding={adoptingId === openProduct.source_id}
          added={adoptedIds.includes(openProduct.source_id)}
          onAdd={(p) => { void adoptProduct(p); setOpenProduct(null); }}
          onClose={() => setOpenProduct(null)}
        />
      )}

      {step === "checkout" && (
        <CustomerInfoForm
          items={cart.items}
          subtotal={cart.subtotal}
          tax={cart.tax}
          total={cart.total}
          position={geo.position}
          onSubmit={handlePlaceOrder}
          onCancel={() => setStep("chat")}
          isLoading={placingOrder}
        />
      )}

      {step === "confirmed" && (confirmedOrder || paidOrderId !== null) && (
        <OrderConfirmation
          order={confirmedOrder}
          orderId={confirmedOrder?.order_id ?? (paidOrderId as number)}
          awaitingConfirmation={awaitingConfirmation}
          paid={paidOrderId !== null}
          onStartNewOrder={startNewOrder}
        />
      )}
    </div>
  );
}
