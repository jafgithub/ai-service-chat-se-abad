"use client";

import { useCallback, useEffect, useState } from "react";
import { docsApi, type CommunityOption } from "@/lib/api/endpoints";

/**
 * Which association the resident is asking as.
 *
 * Chosen once and remembered, rather than asked on every question. A dropdown
 * that reappears each time is a toll on the common case, and the common case is
 * a resident of one community asking about their own home. So: pick once, see
 * it on screen from then on, change it in one tap when the answer is not the
 * one you expected.
 *
 * Kept in localStorage rather than on the session, because a resident's
 * community does not change between visits, and both the floating panel and the
 * booking chat read the same key so a choice made in one applies to the other.
 */
const KEY = "sa_community";

export function storedCommunity(): string {
  try {
    return localStorage.getItem(KEY) ?? "";
  } catch {
    // Private windows and blocked site data both throw here. A resident with
    // no storage still gets answers, from the home community.
    return "";
  }
}

export function rememberCommunity(key: string): void {
  try {
    localStorage.setItem(KEY, key);
  } catch {
    // Private windows and blocked site data both throw. The choice then lasts
    // as long as the page does, which is better than refusing to record it.
  }
}

export function useCommunities() {
  const [options, setOptions] = useState<CommunityOption[]>([]);
  const [home, setHome] = useState("");
  const [chosen, setChosen] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    docsApi
      .communities(controller.signal)
      .then((list) => {
        setOptions(list.communities);
        setHome(list.home);
        const saved = storedCommunity();
        // A saved community whose documents have since been removed must not
        // silently scope every answer to nothing.
        const valid = list.communities.some((c) => c.key === saved);
        setChosen(valid ? saved : "");
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
    return () => controller.abort();
  }, []);

  const choose = useCallback((key: string) => {
    setChosen(key);
    try {
      localStorage.setItem(KEY, key);
    } catch {
      // Not fatal: the choice lasts as long as the page does.
    }
  }, []);

  /** What to show as the current community, falling back to home. */
  const current = options.find((c) => c.key === (chosen || home));

  return { options, chosen, current, choose, loaded, needsChoice: loaded && !chosen && options.length > 1 };
}
