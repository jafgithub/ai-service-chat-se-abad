"use client";

import { apiBase, type DocumentResult } from "@/lib/api";

/**
 * Documents the assistant found by name, drawn where the services usually are.
 *
 * The client's example was "can you get me Application for occupancy for
 * serenity point ... it shows link to the document", so what a resident wants
 * here is the file, not a summary of it. The card is therefore mostly a link.
 *
 * Whether a document can be answered from is said on the card rather than
 * discovered later. Several of these are scans with no readable text: the file
 * is genuinely useful and the assistant genuinely cannot quote it, and somebody
 * who downloads a site map and then asks a question about it should not have to
 * find that out from a refusal.
 */

interface DocumentResultsProps {
  documents: DocumentResult[];
}

export function DocumentResults({ documents }: DocumentResultsProps) {
  return (
    <ul className="space-y-3">
      {documents.map((doc) => (
        <li key={doc.id}>
          <a
            href={`${apiBase}${doc.download_url}`}
            className="flex items-start gap-3 rounded-card border border-line bg-surface p-4 transition-shadow hover:shadow-card-hover"
          >
            <span
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-control bg-brand-50 text-brand-600"
              aria-hidden
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v12m0 0-4-4m4 4 4-4" />
                <path strokeLinecap="round" d="M5 19h14" />
              </svg>
            </span>

            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-ink">{doc.title}</span>
              <span className="mt-0.5 block text-xs text-ink-muted">{doc.community}</span>
              {!doc.answerable && (
                <span className="mt-1.5 block text-xs text-ink-faint">
                  A scan. Yours to download, but I cannot answer questions from it.
                </span>
              )}
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}
