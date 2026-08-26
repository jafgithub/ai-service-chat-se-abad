"use client";

import { useMemo, useState } from "react";

import type { CommunityOption } from "@/lib/api";

/**
 * Choosing an association, in the conversation.
 *
 * Built for a hundred rather than for six. Six fit on screen as buttons and a
 * search box over them is mild overkill; a hundred do not fit at all, and a
 * resident hunting for "Enclave At Old Cutler" in an alphabetical wall is the
 * failure this avoids. So: a filter as soon as there is enough to filter, and a
 * list that scrolls in its own height either way.
 *
 * Each row says what that association actually holds. Kendall Square has one
 * colour sheet and nothing else, and a resident who learns that after asking
 * about the quiet hours has wasted the only question they came to ask. That
 * happened, five times in forty six seconds, on 26 August.
 */

interface CommunityChooserProps {
  options: CommunityOption[];
  onChoose: (key: string) => void;
}

/** What a community holds, in the fewest words that are still true. */
function holdings(option: CommunityOption): string {
  const count = option.documents ?? 0;
  if (count === 0) return "nothing loaded yet";
  // One document is better named than counted: "1 document" tells a resident
  // nothing, and "Approved colour archive" tells them whether to bother.
  if (count === 1 && option.titles?.length) return option.titles[0];
  return `${count} documents`;
}

export function CommunityChooser({ options, onChoose }: CommunityChooserProps) {
  const [filter, setFilter] = useState("");

  const needle = filter.trim().toLowerCase();
  const matching = useMemo(
    () => options.filter((o) => !needle || o.label.toLowerCase().includes(needle)),
    [options, needle],
  );

  return (
    <div className="mt-3">
      {options.length > 4 && (
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={`Search ${options.length} communities`}
          aria-label="Search communities"
          className="mb-2 h-9 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-faint focus:border-brand-300"
        />
      )}

      {matching.length === 0 ? (
        <p className="px-1 py-2 text-sm text-ink-muted">
          No community matches that. Check the spelling, or ask the office to
          have yours added.
        </p>
      ) : (
        <ul className="max-h-56 space-y-1.5 overflow-y-auto">
          {matching.map((option) => (
            <li key={option.key}>
              <button
                type="button"
                onClick={() => onChoose(option.key)}
                className="flex w-full items-baseline justify-between gap-3 rounded-control border border-line bg-surface px-3 py-2 text-left transition-colors hover:border-brand-300 hover:bg-brand-50"
              >
                <span className="text-sm font-medium text-ink">{option.label}</span>
                <span className="flex-shrink-0 text-[11.5px] text-ink-faint">
                  {holdings(option)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
