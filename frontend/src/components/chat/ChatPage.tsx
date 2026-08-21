"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChatMessage } from "./ChatMessage";
import { ServiceCard } from "@/components/booking/ServiceCard";
import { BookingFlow } from "@/components/booking/BookingFlow";
import { AccountMenu } from "@/components/layout/AccountMenu";

import { useAuth } from "@/components/auth/AuthProvider";
import { useGeolocation } from "@/hooks/useGeolocation";
import { getSessionId } from "@/lib/session";
import { chatApi, requestsApi, voiceApi, ApiError } from "@/lib/api";
import type { Booked, ServiceResult } from "@/lib/api";
import { BRAND_NAME, SERVICE_CATEGORIES } from "@/constants";
import type { ChatMessage as ChatMessageType } from "@/types";
import { cn } from "@/lib/utils";

interface ChatPageProps {
  scope?: string;
  onBack: () => void;
}

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

// How many results to put on screen at once. Nothing is hidden: "Show more"
// reveals the next page and the true total is stated.
const PAGE_SIZE = 24;

// Relevance is the order the search already returns, so it costs nothing to
// keep as the default. Price is a guide figure here, which is why the label
// says so: the provider sets the real one.
const SORT_OPTIONS = [
  { id: "relevance", label: "Best match" },
  { id: "price_asc", label: "Lowest guide price" },
] as const;

type SortBy = (typeof SORT_OPTIONS)[number]["id"];

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
  return SERVICE_CATEGORIES.find((c) => c.chatScope === scope) ?? null;
}

/**
 * The assistant, and what it finds.
 *
 * What it was: describe a product, see products, add them to a cart, check out.
 * What it is: describe a problem, see the services that answer it, pick one,
 * and the booking flow takes over from there.
 *
 * The conversation itself is untouched, deliberately. The voice loop, the
 * phrase matching and the reference resolution ("book item 2") are the parts of
 * this product that took the longest to get right, and none of them care
 * whether the thing being matched is a tin of tomatoes or a blocked drain.
 */
export function ChatPage({ scope, onBack }: ChatPageProps) {
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [services, setServices] = useState<ServiceResult[]>([]);
  // How many of `services` are on screen. Reset whenever a new set arrives, so
  // page 3 of one search never carries into the next.
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  // What the results are answering, so the panel can say so.
  const [resultsFor, setResultsFor] = useState("");
  /* The last reply came out of the community documents rather than the
     catalogue. Both leave the results pane empty, and until this existed both
     read the same on screen: an answer about the quiet hours sat beside
     "Nobody on the platform lists anything like that", which is true of the
     catalogue and beside the point of what was asked. */
  const [fromDocuments, setFromDocuments] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("relevance");
  const [totalMatches, setTotalMatches] = useState(0);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // The service being booked, and the problem it answers. Both drive the sheet.
  const [booking, setBooking] = useState<ServiceResult | null>(null);
  const [requestId, setRequestId] = useState<number | null>(null);
  // The customer's own words, kept so the recorded request says what they said
  // rather than the name of whatever service happened to match. State rather
  // than a ref because the booking sheet reads it while rendering.
  const [problem, setProblem] = useState("");

  const auth = useAuth();

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

  const geo = useGeolocation();
  const category = getCategoryInfo(scope);

  /* Named for this product, not the shop it grew out of. The old keys are
     deliberately abandoned rather than migrated: what they hold is a grocery
     conversation ("What products are you looking for today?") with a basket of
     tinned goods beside it, and restoring that into a booking assistant is
     worse than starting fresh. A browser that has both simply ignores the old
     pair, which fall out of localStorage on their own. */
  const STORAGE_KEY = "sa_conversation";
  const RESULTS_KEY = "sa_services";

  const addMessage = useCallback((role: "user" | "assistant", content: string,
                                  sources?: { section: string; document: string }[]) => {
    setMessages((prev) => [...prev,
      { id: crypto.randomUUID(), role, content, timestamp: new Date(), sources }]);
  }, []);

  /**
   * Picking a service, which is where booking starts.
   *
   * The problem is recorded here rather than at the end, and that is the whole
   * argument for keeping requests apart from bookings: most of these never
   * become an appointment, and those are the ones the office needs to see. It
   * needs an account, so for somebody signed out the description travels into
   * the flow and is written the moment they sign in.
   */
  const chooseService = useCallback((service: ServiceResult) => {
    setBooking(service);
    setRequestId(null);

    if (auth.status !== "signed-in" || !problem.trim()) return;
    requestsApi
      .create({ description: problem.trim(), service_id: service.id })
      .then((created) => setRequestId(created.id))
      // Not fatal, and deliberately silent. Failing to file the paperwork must
      // not stop somebody booking a plumber; the booking carries on without it.
      .catch(() => {});
  }, [auth.status, problem]);

  // ── Continuous voice ───────────────────────────────────────────
  // The whole turn runs on the server: it hears the clip, works out what was
  // meant, searches, and sends back the spoken reply. The browser only records
  // and plays.
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

  /** What the assistant did, applied to the screen.
   *
   *  "added" is the interesting one. The intent engine still calls choosing a
   *  service "adding", because that is the phrase the matcher was built around,
   *  but what the customer said was "book item 2" and what they want next is a
   *  provider. So the action opens the booking flow rather than filling a
   *  basket. */
  const applyAction = useCallback((
    action: { type: string; items?: { item_id: number }[] } | null,
    found: ServiceResult[],
  ) => {
    if (!action) return;
    if (action.type !== "added" && action.type !== "checkout") return;

    const wantedId = action.items?.[0]?.item_id;
    const target =
      (wantedId != null ? found.find((s) => s.id === wantedId) : undefined) ??
      // A "checkout" with nothing named means "get on with it", and the only
      // sensible reading is the best match on screen.
      found[0];
    if (target) chooseService(target);
  }, [chooseService]);

  // One turn: record → POST the audio to /voice → play the spoken reply → loop.
  // A single request covers speech-to-text, intent, the search and the reply, so
  // what the assistant heard and what it answered can never disagree.
  const voiceTurn = useCallback(async () => {
    if (!voiceActiveRef.current) return;

    const clip = await recordUtterance();
    if (!voiceActiveRef.current) return;
    if (!clip) {                                       // silence: listen again, no API call
      setTimeout(() => voiceTurnRef.current(), 300);
      return;
    }

    setIsLoading(true);
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
      addMessage("assistant", res.reply, res.sources);
      if (res.services.length > 0) {
        setProblem(heard);
        setServices(res.services);
        setTotalMatches(res.total_services ?? res.services.length);
        setVisibleCount(PAGE_SIZE);
        setResultsFor(heard);
        setFromDocuments("");
      } else if (res.action === null) {
        setServices([]);
        setTotalMatches(0);
        setVisibleCount(PAGE_SIZE);
        const doc = res.intent === "documents" || res.intent === "documents_miss";
        setResultsFor(doc ? "" : heard);
        setFromDocuments(doc ? res.intent! : "");
      }
      applyAction(res.action, res.services.length > 0 ? res.services : services);
      // Speak the short version: long lists are shown, not read out.
      await speak(res.audio ?? "", res.speech || res.reply);
    } catch {
      setIsLoading(false);
      addMessage("assistant", "Sorry, I couldn't process that. Please try again.");
    }

    if (voiceActiveRef.current) voiceTurnRef.current();      // keep the conversation going
  }, [recordUtterance, speak, sessionId, scope, geo.position, addMessage, applyAction, services]);

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
            const savedResults = localStorage.getItem(RESULTS_KEY);
            if (savedResults) setServices(JSON.parse(savedResults));
            inputRef.current?.focus();
            return;
          }
        } catch {
          localStorage.removeItem(STORAGE_KEY);
          localStorage.removeItem(RESULTS_KEY);
        }
      }

      const greeting = scope
        ? `Hi 👋 I can help with **${scope}**. What has gone wrong?`
        : "Hi 👋 I'm your booking assistant. Tell me what needs doing and I will find someone who does it.";
      setMessages([{ id: crypto.randomUUID(), role: "assistant", content: greeting, timestamp: new Date() }]);
      inputRef.current?.focus();
    }
    void init();
    // Stop any voice/audio when leaving the page.
    return () => stopVoice();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (messages.length > 0) localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    if (services.length > 0) localStorage.setItem(RESULTS_KEY, JSON.stringify(services));
  }, [services]);

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
      addMessage("assistant", response.reply, response.sources);
      // A search that found nothing has to clear the last one, or the assistant
      // says "I couldn't find anything" beside a panel still listing results for
      // the previous question. Only a *search* clears them: choosing a service
      // also returns an empty list, and that must leave what is on screen alone.
      if (response.services.length > 0) {
        setProblem(text.trim());
        setServices(response.services);
        setTotalMatches(response.total_services ?? response.services.length);
        setVisibleCount(PAGE_SIZE);
        setResultsFor(text.trim());
        setFromDocuments("");
      } else if (response.action === null) {
        // A documents answer is not a failed search and must not be dressed as
        // one. Clearing `resultsFor` keeps "Nothing matches" off the screen;
        // the flag puts something honest there instead.
        setServices([]);
        setTotalMatches(0);
        setVisibleCount(PAGE_SIZE);
        const doc = response.intent === "documents" || response.intent === "documents_miss";
        setResultsFor(doc ? "" : text.trim());
        setFromDocuments(doc ? response.intent! : "");
      }
      applyAction(response.action, response.services.length > 0 ? response.services : services);
    } catch (err) {
      const msg = err instanceof ApiError
        ? `Sorry, something went wrong: ${err.detail}`
        : "Sorry, I couldn't connect to the server. Please try again.";
      addMessage("assistant", msg);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, scope, geo.position, sessionId, addMessage, applyAction, services]);

  const onBooked = useCallback((made: Booked) => {
    addMessage(
      "assistant",
      `Done. **${made.provider_name}** will attend on ${made.label}. ` +
      `Your reference is **${made.reference}**.`
    );
  }, [addMessage]);

  /* Deliberately not the category names: the results pane already offers those
     as cards, and showing the same set twice on one screen made the page look
     like it had one idea. These prompt the thing the product is actually for,
     which is describing a problem in your own words. */
  const quickReplies = scope
    ? ["What does that involve?", "What does it usually cost?", "Show me everything"]
    : ["My kitchen sink is blocked", "My dog needs his vaccinations", "I need an end of tenancy clean"];

  const micActive = isListening || isSpeaking;

  /* Sorted before paging, so "lowest" means the cheapest of everything that
     matched rather than the cheapest of the 24 on screen. A copy, because
     Array.sort mutates and this is state. */
  const sortedServices = useMemo(() => {
    if (sortBy !== "price_asc") return services;
    return [...services].sort((a, b) => a.price_per_unit - b.price_per_unit);
  }, [services, sortBy]);

  const visible = sortedServices.slice(0, visibleCount);
  const hasMore = sortedServices.length > visibleCount;
  // A search ran and matched nothing, as opposed to nobody having asked yet.
  // The two look identical in state and must not read the same on screen.
  const searchedAndFoundNothing = services.length === 0 && resultsFor !== "";

  /* Defined once, rendered twice: pinned under the conversation on a wide
     screen, and as a shared footer on a phone. */
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
    <div className="flex h-dvh flex-col overflow-hidden bg-surface-sunken pb-[env(safe-area-inset-bottom)]">

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
              <span className={cn("h-1.5 w-1.5 rounded-full bg-white", micActive && "animate-pulse")} />
              <span className="text-xs text-white/85">
                {micActive ? (isSpeaking ? "Speaking" : "Listening") : "Online"}
              </span>
            </div>
          </div>

          {/* Where the cart used to be. */}
          <AccountMenu onBrand />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">

        {/* ── Conversation ─────────────────────────────────────────────── */}
        <div className="flex w-full flex-shrink-0 flex-col border-r border-line bg-surface lg:w-[440px] xl:w-[500px]">

          {/* Phone only: results swipe sideways above the conversation, so both
              are on screen at once. */}
          {(services.length > 0 || isLoading) && (
            <div className="flex-shrink-0 border-b border-line bg-surface-sunken lg:hidden">
              <div className="flex items-baseline justify-between px-4 pb-1.5 pt-2.5">
                <p className="text-xs font-medium text-ink">
                  {isLoading
                    ? "Looking…"
                    : `${totalMatches || services.length} service${(totalMatches || services.length) === 1 ? "" : "s"}`}
                </p>
                {!isLoading && services.length > 1 && (
                  <button
                    onClick={() => setSortBy((v) => (v === "relevance" ? "price_asc" : "relevance"))}
                    className="text-[11px] font-semibold text-brand-600"
                  >
                    {sortBy === "relevance" ? "Best match" : "Lowest guide price"}
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
                        className="h-56 w-[150px] flex-shrink-0 animate-pulse rounded-card border border-line bg-surface"
                      />
                    ))
                  : (
                    <>
                      {visible.map((service) => (
                        <div key={service.id} className="w-[150px] flex-shrink-0 snap-start">
                          <ServiceCard service={service} onChoose={chooseService} compact />
                        </div>
                      ))}

                      {hasMore && (
                        <button
                          onClick={() => setVisibleCount((n) => n + PAGE_SIZE)}
                          className="flex w-[130px] flex-shrink-0 snap-start flex-col items-center justify-center gap-1 rounded-card border border-dashed border-line-strong bg-surface text-sm font-medium text-ink-muted"
                        >
                          <span className="text-lg" aria-hidden>+</span>
                          Show {Math.min(PAGE_SIZE, sortedServices.length - visibleCount)} more
                        </button>
                      )}
                    </>
                  )}
              </div>
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

          {composer}
        </div>

        {/* ── What we can do about it ──────────────────────────────────── */}
        <div className="hidden flex-1 flex-col overflow-hidden bg-surface-sunken lg:flex">

          <div className="flex flex-shrink-0 items-center justify-between gap-4 border-b border-line bg-surface px-6 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">
                {services.length > 0
                  ? resultsFor
                    ? `For “${resultsFor}”`
                    : "Services"
                  : fromDocuments === "documents_miss"
                    ? "Not in the community documents"
                    : fromDocuments
                      ? "From the community documents"
                    : searchedAndFoundNothing
                      ? `Nothing matches “${resultsFor}”`
                      : "Services"}
              </p>
              <p className="mt-0.5 text-xs text-ink-muted">
                {services.length > 0
                  ? totalMatches > services.length
                    ? `${totalMatches} match, showing the closest ${services.length}`
                    : `${services.length} service${services.length === 1 ? "" : "s"} could cover this`
                  : fromDocuments === "documents_miss"
                    ? "Nothing in them covers that, so nothing was invented"
                    : fromDocuments
                      ? "The answer is in the conversation, with the rule it came from"
                    : searchedAndFoundNothing
                      ? "Nobody on the platform lists anything like that"
                    : "Describe the problem, or start from a category"}
              </p>
            </div>

            {services.length > 1 && (
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

          <div className="chat-scroll flex-1 overflow-y-auto px-5 py-5">
            {isLoading ? (
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-4">
                {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                  <div key={i} className="overflow-hidden rounded-card border border-line bg-surface">
                    <div className="h-24 w-full animate-pulse bg-surface-hover" />
                    <div className="space-y-2 p-3">
                      <div className="h-3 w-3/4 animate-pulse rounded bg-surface-hover" />
                      <div className="h-3 w-1/2 animate-pulse rounded bg-surface-hover" />
                      <div className="mt-2 h-10 w-full animate-pulse rounded-control bg-surface-hover" />
                    </div>
                  </div>
                ))}
              </div>
            ) : services.length > 0 ? (
              <>
                <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-4">
                  {visible.map((service) => (
                    <ServiceCard key={service.id} service={service} onChoose={chooseService} />
                  ))}
                </div>

                {hasMore && (
                  <div className="mt-5 flex flex-col items-center gap-1.5">
                    <button
                      onClick={() => setVisibleCount((n) => n + PAGE_SIZE)}
                      className="h-11 rounded-control border border-line bg-surface px-6 text-sm font-medium text-ink transition-colors hover:bg-surface-hover"
                    >
                      Show {Math.min(PAGE_SIZE, sortedServices.length - visibleCount)} more
                    </button>
                    <p className="text-xs text-ink-faint">
                      {sortedServices.length - visibleCount} more to see
                    </p>
                  </div>
                )}
              </>
            ) : (
              /* The arrival state: somewhere to start rather than an empty pane. */
              <div className={cn("flex h-full flex-col justify-center")}>
                <div className="mx-auto w-full max-w-2xl">
                  <h2 className="text-base font-semibold text-ink">
                    {fromDocuments === "documents_miss"
                      ? "Not in the community documents"
                      : fromDocuments
                      ? "Answered from the community documents"
                      : searchedAndFoundNothing
                        ? `Nothing here matches “${resultsFor}”`
                        : "What needs doing?"}
                  </h2>
                  <p className="mt-1 text-sm text-ink-muted">
                    {fromDocuments === "documents_miss"
                      ? "Ask about a particular thing and I will look it up, or describe a job and I will find someone."
                      : fromDocuments
                      ? "Ask another question about the rules, or describe a job and I will find someone."
                      : searchedAndFoundNothing
                        ? "Try describing it differently, or start from a category."
                        : "Describe it in your own words, or start from a category."}
                  </p>

                  <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                    {SERVICE_CATEGORIES.map((cat) => (
                      <button
                        key={cat.id}
                        onClick={() => sendMessage(`I need help with ${cat.title}`)}
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
        </div>
      </div>

      {booking && (
        <BookingFlow
          service={booking}
          serviceRequestId={requestId}
          problem={problem}
          onClose={() => setBooking(null)}
          onBooked={onBooked}
        />
      )}
    </div>
  );
}
