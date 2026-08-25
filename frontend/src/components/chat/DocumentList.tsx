"use client";

import { apiBase, type DocumentResult } from "@/lib/api";

/**
 * The documents behind an answer, listed under it in the conversation.
 *
 * Two ways into the same file, because they are two different intentions. The
 * title opens the PDF in a tab: somebody checking one line of a rule should not
 * have to put 900KB in their downloads to read it. The icon at the end saves
 * it: somebody who wants the blank ARB form to fill in does.
 *
 * The row carries the section as well as the document, because "Rules and
 * Regulations" is 55 sections long and "Rule 18: Unnecessary and excessive
 * noises" is where the answer came from. Without it a resident opens the PDF
 * and starts reading page one.
 *
 * Deduplication happens on the server, by document. Three rules quoted from one
 * handbook is one thing to download, and listing it three times reads as three
 * documents.
 */

interface DocumentListProps {
  documents: DocumentResult[];
  /** "FROM YOUR DOCUMENTS" over an answer's sources, nothing over a list that
   *  was asked for by name and needs no explaining. */
  heading?: string;
}

export function DocumentList({ documents, heading }: DocumentListProps) {
  if (documents.length === 0) return null;

  return (
    <div className="mt-3 overflow-hidden rounded-control border border-line">
      {heading && (
        <p className="border-b border-line bg-surface-sunken px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-ink-faint">
          {heading}
        </p>
      )}

      <ul className="divide-y divide-line">
        {documents.map((doc) => (
          <li key={doc.id} className="flex items-center gap-2 bg-surface transition-colors hover:bg-surface-sunken">
            <a
              href={`${apiBase}${doc.view_url || doc.download_url}`}
              target="_blank"
              rel="noopener noreferrer"
              className="min-w-0 flex-1 px-3 py-2.5"
            >
              <span className="block truncate text-[13px] font-semibold text-ink">
                {doc.title}
              </span>
              <span className="mt-0.5 block truncate text-[11.5px] text-ink-muted">
                {doc.community}
                {doc.section ? ` · ${doc.section}` : ""}
              </span>
              {!doc.answerable && (
                <span className="mt-0.5 block text-[11.5px] text-ink-faint">
                  A scan. Yours to open and keep, but I cannot answer from it.
                </span>
              )}
            </a>

            <a
              href={`${apiBase}${doc.download_url}`}
              download
              title={`Download ${doc.title}`}
              aria-label={`Download ${doc.title}`}
              className="mr-2 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control text-ink-faint transition-colors hover:bg-brand-50 hover:text-brand-600"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.9} viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v11m0 0-3.5-3.5M12 15l3.5-3.5" />
                <path strokeLinecap="round" d="M5 19h14" />
              </svg>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
