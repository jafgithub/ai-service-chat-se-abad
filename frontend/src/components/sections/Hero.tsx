"use client";

import { Button } from "@/components/ui/Button";

interface HeroProps {
  onStartOrdering: () => void;
  onPartnerClick: () => void;
}

export function Hero({ onStartOrdering, onPartnerClick }: HeroProps) {
  return (
    <section
      id="hero"
      className="relative flex min-h-[86svh] items-center justify-center overflow-hidden bg-gradient-to-br from-orange-50 via-amber-50 to-rose-50 py-20 sm:min-h-screen sm:py-0"
    >
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <div className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full bg-orange-200/40 blur-3xl" />
        <div className="absolute -bottom-24 -left-24 w-[500px] h-[500px] rounded-full bg-rose-200/40 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full bg-amber-100/30 blur-3xl" />
      </div>

      <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden>
        {["🔧", "🐾", "🏠", "⚡", "🧹", "📅"].map((emoji, i) => (
          <span
            key={i}
            /* Hidden on phones: at 414px these land directly on top of the
               headline and the body copy, and a broccoli sitting in the middle
               of a sentence is not decoration, it is interference. */
            className="absolute hidden select-none text-4xl opacity-10 animate-pulse sm:block"
            style={{
              top: `${10 + i * 14}%`,
              left: `${5 + i * 15}%`,
              animationDelay: `${i * 0.5}s`,
              animationDuration: `${3 + i * 0.4}s`,
            }}
          >
            {emoji}
          </span>
        ))}
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div className="inline-flex items-center gap-2 bg-white/80 backdrop-blur-sm border border-orange-200 rounded-full px-4 py-2 text-sm font-medium text-orange-700 mb-8 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
          AI-Powered Ordering — Available 24/7
        </div>
        {/* `text-balance` plus a break at every size. The break used to be
            hidden below `sm`, which left "Book a Plumber. Just" as the shortest
            line the heading could make; "Smarter." is an inline-block so it
            cannot break inside, and at 48px that line is wider than a phone.
            The whole centred column grew with it and the buttons ran off the
            right edge of every screen narrower than about 480px. */}
        <h1 className="mb-6 text-balance text-4xl font-extrabold leading-tight tracking-tight text-gray-900 sm:text-6xl lg:text-7xl">
          Order{" "}
          <span className="relative inline-block">
            <span className="relative z-10 text-orange-500">Smarter.</span>
            <span
              className="absolute inset-x-0 bottom-1 h-3 bg-orange-200 rounded-full -z-0"
              aria-hidden
            />
          </span>{" "}
          <br />
          Just Ask.
        </h1>
        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-gray-600 leading-relaxed mb-10">
          Chat or speak to our AI — find products, get pricing, and place your
          order in minutes. No app downloads, no waiting in line.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button size="lg" onClick={onStartOrdering} className="w-full sm:w-auto">
            <span>Start Ordering</span>
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </Button>
          <Button variant="outline" size="lg" className="w-full sm:w-auto" onClick={onPartnerClick}>
            Want to be partner with us?
          </Button>
        </div>
        <div className="mt-12 flex flex-wrap items-center justify-center gap-6 text-sm text-gray-500">
          {["Instant order confirmation", "Email receipt included", "Voice & text support"].map(
            (item) => (
              <div key={item} className="flex items-center gap-2">
                <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                {item}
              </div>
            )
          )}
        </div>
      </div>
      <div className="absolute bottom-6 left-1/2 hidden -translate-x-1/2 flex-col items-center gap-1 text-gray-400 animate-bounce sm:flex">
        <span className="text-xs font-medium">Scroll</span>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </section>
  );
}
