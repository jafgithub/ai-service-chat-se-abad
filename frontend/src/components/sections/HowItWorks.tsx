import { HOW_IT_WORKS_STEPS } from "@/constants";

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24 bg-surface">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <span className="inline-block text-sm font-semibold uppercase tracking-widest text-brand-500 mb-3">
            Simple Process
          </span>
          <h2 className="text-4xl sm:text-5xl font-extrabold text-ink mb-4">
            How It Works
          </h2>
          <p className="max-w-xl mx-auto text-lg text-ink-muted">
            Three steps between a problem and somebody booked to fix it.
          </p>
        </div>

        <div className="relative">
          <div
            className="hidden lg:block absolute top-16 left-[calc(16.666%+2rem)] right-[calc(16.666%+2rem)] h-0.5 bg-gradient-to-r from-orange-200 via-orange-400 to-orange-200"
            aria-hidden
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 lg:gap-8 relative">
            {HOW_IT_WORKS_STEPS.map((step) => (
              <div
                key={step.number}
                className="flex flex-col items-center text-center group"
              >
                <div className="relative mb-6">
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-orange-400 to-rose-500 flex items-center justify-center text-4xl shadow-lg shadow-orange-200 group-hover:scale-110 transition-transform duration-300">
                    {step.icon}
                  </div>
                  <div className="absolute -top-2 -right-2 w-7 h-7 rounded-full bg-gray-900 text-white text-xs font-bold flex items-center justify-center ring-2 ring-white">
                    {step.number}
                  </div>
                </div>

                <h3 className="text-xl font-bold text-ink mb-3">{step.title}</h3>
                <p className="text-ink-muted leading-relaxed">{step.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-16 text-center">
          <div className="inline-flex items-center gap-3 bg-brand-50 border border-orange-100 rounded-card px-6 py-4">
            <span className="text-2xl">⚡</span>
            <p className="text-ink-muted font-medium">
              Most bookings are made in under{" "}
              <span className="text-brand-500 font-bold">3 minutes</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
