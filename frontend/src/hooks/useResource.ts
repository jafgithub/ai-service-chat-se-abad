"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";

/**
 * Fetching one thing from the API, with the three outcomes every screen needs.
 *
 * Written once because a dozen pages were writing it, and writing it slightly
 * differently: some cleared the old data before fetching and some did not, so
 * changing tab showed the previous tab's rows for a moment as though they were
 * the new ones.
 *
 * The interesting part is how staleness is handled. The obvious approach is to
 * clear the data at the top of the effect, and React now warns about it,
 * rightly: setting state synchronously in an effect body causes a second render
 * pass every time. Instead the data is stored with the key it was fetched for,
 * and the key is compared during render. Data belonging to a key we are no
 * longer asking about is simply not returned, so nothing has to be cleared and
 * a stale row can never be drawn.
 *
 * `reload` exists because "try again" is the right answer to most failures
 * here, and a retry that cannot be triggered is a dead end.
 */

interface Resource<T> {
  data: T | null;
  /** The message to show. Null when nothing has gone wrong. */
  error: string | null;
  /** The HTTP status, when there was one. 404 and 503 mean different things to
   *  a booking screen and must be distinguishable. */
  status: number | null;
  loading: boolean;
  reload: () => void;
}

interface Options {
  /** Skip the call entirely, e.g. while it is not yet known who is signed in. */
  enabled?: boolean;
  /** Shown when the failure was not an ApiError, i.e. the wire rather than the server. */
  offlineMessage?: string;
}

export function useResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  /** Everything the fetch depends on. Changing any of them refetches, and the
   *  previous answer stops being shown at once. */
  deps: readonly unknown[],
  options: Options = {}
): Resource<T> {
  const { enabled = true, offlineMessage = "We could not reach the server." } = options;

  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    key: string;
    data: T | null;
    error: string | null;
    status: number | null;
  } | null>(null);

  const key = JSON.stringify([deps, attempt, enabled]);

  // The freshest fetcher, so the effect does not rerun when a caller passes an
  // inline arrow function, which is every caller.
  const fetcherRef = useRef(fetcher);
  useEffect(() => { fetcherRef.current = fetcher; });

  useEffect(() => {
    if (!enabled) return;

    const controller = new AbortController();
    let dropped = false;

    fetcherRef.current(controller.signal)
      .then((data) => {
        if (!dropped) setState({ key, data, error: null, status: null });
      })
      .catch((err) => {
        if (dropped || controller.signal.aborted) return;
        setState({
          key,
          data: null,
          error: err instanceof ApiError ? err.detail : offlineMessage,
          status: err instanceof ApiError ? err.status : null,
        });
      });

    return () => {
      dropped = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Only an answer to the question currently being asked. Anything else is a
  // previous question's answer and counts as still loading.
  const fresh = state?.key === key ? state : null;

  return {
    data: fresh?.data ?? null,
    error: fresh?.error ?? null,
    status: fresh?.status ?? null,
    loading: enabled && fresh === null,
    reload: useCallback(() => setAttempt((n) => n + 1), []),
  };
}
