"use client";

import { SERVICE_CATEGORIES } from "@/constants";
import type { ServiceCategory } from "@/types";

interface ServiceCategoriesProps {
  onCategorySelect: (scope: string) => void;
}

function CategoryTile({
  category,
  onSelect,
}: {
  category: ServiceCategory;
  onSelect: (scope: string) => void;
}) {
  return (
    <button
      onClick={() => onSelect(category.chatScope)}
      className="group relative flex flex-col items-center text-center bg-surface rounded-sheet p-8 shadow-md hover:shadow-xl border border-line hover:border-transparent transition-all duration-300 hover:-translate-y-2 focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 overflow-hidden"
      aria-label={`Find help with ${category.title}`}
    >
      <div
        className={`absolute inset-0 bg-gradient-to-br ${category.color} opacity-0 group-hover:opacity-5 transition-opacity duration-300`}
        aria-hidden
      />

      <div
        className={`w-20 h-20 rounded-card bg-gradient-to-br ${category.color} flex items-center justify-center text-4xl mb-5 shadow-lg group-hover:scale-110 transition-transform duration-300`}
      >
        {category.icon}
      </div>

      <h3 className="text-xl font-bold text-ink mb-2">{category.title}</h3>
      <p className="text-ink-muted text-sm leading-relaxed mb-6">{category.description}</p>

      <span className="inline-flex items-center gap-2 text-sm font-semibold text-brand-500 group-hover:gap-3 transition-all duration-200">
        Find someone
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </span>
    </button>
  );
}

export function ServiceCategories({ onCategorySelect }: ServiceCategoriesProps) {
  return (
    <section id="services" className="py-24 bg-surface-sunken">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <span className="inline-block text-sm font-semibold uppercase tracking-widest text-brand-500 mb-3">
            What we cover
          </span>
          <h2 className="text-4xl sm:text-5xl font-extrabold text-ink mb-4">
            What needs doing?
          </h2>
          <p className="max-w-xl mx-auto text-lg text-ink-muted">
            Pick a category and the assistant will find the right service and somebody who does it.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {SERVICE_CATEGORIES.map((cat) => (
            <CategoryTile key={cat.id} category={cat} onSelect={onCategorySelect} />
          ))}
        </div>

        <p className="text-center text-ink-faint text-sm mt-10">
          More categories as more providers join.
        </p>
      </div>
    </section>
  );
}
