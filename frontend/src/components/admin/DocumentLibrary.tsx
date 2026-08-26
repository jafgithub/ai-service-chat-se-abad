"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api";
import { docsApi, type CommunityOption } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

/**
 * The community documents, as the office sees them.
 *
 * Adding a document used to mean emailing it to us and waiting for a rebuild.
 * Here it is a file, a community, and a few seconds: the server reads the PDF,
 * cuts it into sections and puts them into the live index, and the assistant
 * answers from it immediately.
 *
 * Two things this screen has to be honest about, because both surprise people.
 *
 *   * A scan cannot be answered from. It is stored and residents can download
 *     it, which is what was asked for, but no text ever comes out of a picture
 *     of a page. The screen says so at the moment it happens rather than
 *     leaving somebody to discover it when the assistant refuses.
 *   * Removing a document changes what residents are told. It stops answering
 *     at once, so the confirmation says which community loses it.
 */

const NEW = "__new__";

interface DocumentRow {
  id: string;
  community: string;
  community_label: string;
  title: string;
  kind: string;
  sections: number;
  added_at: string;
  answerable: boolean;
  download_url: string;
}

const when = (iso: string) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";

export function DocumentLibrary({ token }: { token: string }) {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [communities, setCommunities] = useState<CommunityOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [community, setCommunity] = useState("");
  const [newKey, setNewKey] = useState("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DocumentRow | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const headers = { "X-Admin-Token": token };

  const load = useCallback(async () => {
    try {
      const [rows, list] = await Promise.all([
        apiClient.get<DocumentRow[]>("/api/v1/documents", undefined, headers),
        docsApi.communities(),
      ]);
      setDocs(rows);
      setCommunities(list.communities);
      setCommunity((c) => c || list.communities[0]?.key || NEW);
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load the documents.");
    } finally {
      setLoading(false);
    }
    // `headers` is rebuilt each render from `token`, which is what matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  /* The state updates all happen after an await, because setting state
     synchronously inside an effect triggers a cascading render. Everything
     else here is event driven: uploading and removing call `load` directly. */
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (!cancelled) await load();
    })();
    return () => { cancelled = true; };
  }, [load]);

  const upload = async (event: React.FormEvent) => {
    event.preventDefault();
    const key = community === NEW ? newKey.trim().toLowerCase() : community;
    if (!file || !key) return;

    const form = new FormData();
    form.append("file", file);
    form.append("community", key);
    if (community === NEW) form.append("community_label", newKey.trim());
    if (title.trim()) form.append("title", title.trim());

    setBusy(true);
    setResult(null);
    setError("");
    try {
      const added = await apiClient.postForm<DocumentRow>("/api/v1/documents", form, undefined, headers);
      setResult(added);
      setTitle("");
      setFile(null);
      setNewKey("");
      if (fileRef.current) fileRef.current.value = "";
      if (community === NEW) setCommunity(added.community);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The upload failed.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (doc: DocumentRow) => {
    // Named in the question, because "are you sure" answers nothing: what
    // matters is which community stops being told this.
    const ok = window.confirm(
      `Remove "${doc.title}" from ${doc.community_label}?\n\n` +
      (doc.answerable
        ? "The assistant will stop answering from it straight away."
        : "Residents will no longer be able to download it.")
    );
    if (!ok) return;
    try {
      await apiClient.del(`/api/v1/documents/${doc.id}`, undefined, headers);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not remove it.");
    }
  };

  const grouped = docs.reduce<Record<string, DocumentRow[]>>((acc, doc) => {
    (acc[doc.community_label] ??= []).push(doc);
    return acc;
  }, {});

  /* One document is not a rule book. Two is a community with a couple of forms
     and no rules. Past that it is a judgement call nobody needs a warning
     about. */
  const thin = communities.filter((c) => (c.documents ?? 0) <= 1);

  return (
    <section className="rounded-card border border-line bg-surface">
      <header className="border-b border-line px-5 py-4">
        <h2 className="text-base font-semibold text-ink">Community documents</h2>
        <p className="mt-0.5 text-sm text-ink-muted">
          Add a document and the assistant answers from it within seconds. Scans are
          kept for residents to download, but cannot be answered from.
        </p>
      </header>

      {thin.length > 0 && (
        /* Shown here rather than in a report, because this is the screen that
           fixes it. A resident of one of these can be asked almost nothing:
           on 26 August somebody asked Kendall Square for the quiet hours five
           times in forty six seconds before giving up. */
        <div className="border-b border-line bg-warn-soft px-5 py-3">
          <p className="text-sm font-medium text-warn">
            {thin.length === 1
              ? "One community has almost nothing loaded"
              : `${thin.length} communities have almost nothing loaded`}
          </p>
          <ul className="mt-1.5 space-y-0.5">
            {thin.map((c) => (
              <li key={c.key} className="text-[13px] text-warn">
                <span className="font-medium">{c.label}</span>
                {": "}
                {c.documents === 0
                  ? "nothing at all"
                  : c.titles?.length
                    /* The community's own name is stripped off the front:
                       "Lauderdale Lakes: Lauderdale Lakes code handbook" says
                       it twice, and lowercasing a proper noun to avoid that
                       just looks like a typo. */
                    ? `${c.titles[0].replace(new RegExp(`^${c.label}\\s*`, "i"), "")} only`
                    : `${c.documents} document${c.documents === 1 ? "" : "s"}`}
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-[13px] text-warn">
            Residents there can be asked almost nothing. Add their rules and
            regulations below.
          </p>
        </div>
      )}

      <form onSubmit={upload} className="grid gap-3 border-b border-line px-5 py-4 sm:grid-cols-2">
        <label className="text-sm">
          <span className="mb-1 block font-medium text-ink">Community</span>
          <select
            value={community}
            onChange={(e) => setCommunity(e.target.value)}
            className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
          >
            {communities.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
            <option value={NEW}>Add a new community...</option>
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block font-medium text-ink">
            {community === NEW ? "Name of the community" : "Title (optional)"}
          </span>
          <input
            value={community === NEW ? newKey : title}
            onChange={(e) => (community === NEW ? setNewKey : setTitle)(e.target.value)}
            placeholder={community === NEW ? "Harbour View" : "Taken from the file name"}
            className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
          />
        </label>

        {community === NEW && (
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium text-ink">Title (optional)</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Taken from the file name"
              className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
            />
          </label>
        )}

        <label className="text-sm sm:col-span-2">
          <span className="mb-1 block font-medium text-ink">PDF</span>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full rounded-control border border-line bg-surface px-3 py-2.5 text-sm text-ink file:mr-3 file:rounded-full file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-700"
          />
        </label>

        <div className="flex items-center gap-3 sm:col-span-2">
          <button
            type="submit"
            disabled={busy || !file || (community === NEW && !newKey.trim())}
            className="h-11 rounded-control bg-brand-500 px-5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {busy ? "Reading the document..." : "Add document"}
          </button>
          {busy && (
            <span className="text-sm text-ink-muted">
              This takes a few seconds for a long document.
            </span>
          )}
        </div>

        {result && (
          <p className={cn(
            "rounded-control px-4 py-3 text-sm sm:col-span-2",
            result.answerable
              ? "bg-positive-soft text-positive"
              : "border border-line bg-surface-sunken text-ink"
          )}>
            {result.answerable ? (
              <>
                <strong>{result.title}</strong> is live for {result.community_label}, in{" "}
                {result.sections} section{result.sections === 1 ? "" : "s"}. Ask the
                assistant about it now.
              </>
            ) : (
              <>
                <strong>{result.title}</strong> was stored for {result.community_label} as a
                download. There is no readable text in it, so it is a scan or a drawing and
                the assistant cannot answer from it. Residents can still download it.
              </>
            )}
          </p>
        )}

        {error && (
          <p className="rounded-control bg-danger-soft px-4 py-3 text-sm text-danger sm:col-span-2">
            {error}
          </p>
        )}
      </form>

      <div className="px-5 py-4">
        {loading ? (
          <p className="text-sm text-ink-muted">Loading...</p>
        ) : docs.length === 0 ? (
          <p className="text-sm text-ink-muted">No documents yet.</p>
        ) : (
          Object.entries(grouped).map(([label, rows]) => (
            <div key={label} className="mb-5 last:mb-0">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                {label} · {rows.length} document{rows.length === 1 ? "" : "s"}
              </p>
              <ul className="space-y-2">
                {rows.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-control border border-line px-4 py-3"
                  >
                    <span className="font-medium text-ink">{doc.title}</span>
                    <span className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      doc.answerable
                        ? "bg-positive-soft text-positive"
                        : "bg-surface-sunken text-ink-muted"
                    )}>
                      {doc.answerable ? `${doc.sections} sections` : "download only"}
                    </span>
                    <span className="text-xs text-ink-faint">{when(doc.added_at)}</span>
                    <span className="ml-auto flex items-center gap-3">
                      <a
                        href={doc.download_url}
                        className="text-sm text-ink-muted underline-offset-2 hover:text-ink hover:underline"
                      >
                        Download
                      </a>
                      <button
                        type="button"
                        onClick={() => remove(doc)}
                        className="text-sm font-medium text-danger hover:underline"
                      >
                        Remove
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
