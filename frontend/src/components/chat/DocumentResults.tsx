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
          {/* The whole card used to be one anchor with neither `download` nor
              `target`, so a click navigated the application away and replaced
              it with a PDF. It is now a row: read on the left, save on the
              right, and a button cannot be nested inside an anchor. */}
          <div className="flex items-start gap-3 rounded-card border border-line bg-surface p-4 transition-shadow hover:shadow-card-hover">
          <a
            href={`${apiBase}${doc.view_url || doc.download_url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex min-w-0 flex-1 items-start gap-3"
          >
            <span
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-control bg-brand-50 text-brand-600"
              aria-hidden
            >
              {/* A page, not an arrow. This half opens the document to read;
                  the arrow lives on the Download button, which saves it. */}
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M14 3v5h5M9 13h6M9 17h4" />
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

          <a
            href={`${apiBase}${doc.download_url}`}
            download
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Download ${doc.title}`}
            className="flex flex-shrink-0 items-center gap-1.5 rounded-control border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-ink-muted transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v11m0 0-3.5-3.5M12 15l3.5-3.5" />
              <path strokeLinecap="round" d="M5 19h14" />
            </svg>
            Download
          </a>
          </div>
        </li>
      ))}
    </ul>
  );
}
