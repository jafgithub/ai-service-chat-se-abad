"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { authApi, loadStoredToken, onUnauthorized, setAuthToken } from "@/lib/api";
import type { Account, Role, TokenOut } from "@/lib/api";

/**
 * Who is signed in, for the whole application.
 *
 * There is one token and one session system, the backend's. This holds the
 * account it belongs to and nothing else: no second notion of identity, no
 * permissions worked out in the browser. What a customer or a provider may do
 * is decided by the API, and the guards here only decide what to draw.
 *
 * `status` matters more than it looks. "loading" is not "signed out": a page
 * that treats the moment before /auth/me answers as signed out will flash a
 * sign-in screen at somebody who is already signed in, and worse, will redirect
 * them away from the page they asked for.
 */

export type AuthStatus = "loading" | "signed-in" | "signed-out";

interface AuthValue {
  status: AuthStatus;
  account: Account | null;
  role: Role | null;
  /** True once the token has been checked, whichever way it went. */
  ready: boolean;
  /** Set when a session ended underneath us, so a screen can say why. */
  expired: boolean;
  /** Take the token a login or registration just returned. */
  accept: (token: TokenOut) => Promise<Account | null>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
  clearExpired: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [account, setAccount] = useState<Account | null>(null);
  const [expired, setExpired] = useState(false);
  // Guards the very first check, which must not be repeated by a re-render.
  const started = useRef(false);

  /** Ask the server who this token belongs to.
   *
   *  `token` is only passed on the first call, where "there is no token at all"
   *  has to settle to signed-out without a pointless 401. Afterwards the client
   *  holds it and there is nothing to pass. */
  const load = useCallback(async (token?: string | null) => {
    if (token === null) {
      setAccount(null);
      setStatus("signed-out");
      return;
    }
    try {
      const me = await authApi.me();
      setAccount(me);
      setStatus("signed-in");
    } catch {
      // The client has already cleared the token if the server rejected it.
      setAccount(null);
      setStatus("signed-out");
    }
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    // The token outlives the tab, so the first thing to do is find it. This
    // reads localStorage, which does not exist during the static prerender, so
    // it happens after mount rather than in a state initializer.
    //
    // `load` sets state in its own async continuation either way, including for
    // the no-token case, so the effect body never sets state synchronously and
    // the first paint is always the loading state.
    void load(loadStoredToken());
  }, [load]);

  useEffect(() => {
    // One place handles a token going bad, rather than every caller.
    onUnauthorized(() => {
      setAccount(null);
      setStatus("signed-out");
      setExpired(true);
    });
    return () => onUnauthorized(null);
  }, []);

  const accept = useCallback(async (token: TokenOut) => {
    setAuthToken(token.token);
    setExpired(false);
    try {
      const me = await authApi.me();
      setAccount(me);
      setStatus("signed-in");
      return me;
    } catch {
      // The token was just issued, so this is a network or server problem
      // rather than a bad token. Fall back to what the token response itself
      // told us, which is enough to route somebody to the right screen.
      const stand_in: Account = {
        account_id: 0,
        email: "",
        role: token.role,
        name: token.name,
        customer_id: token.customer_id ?? null,
        provider_id: token.provider_id ?? null,
        provider_status: token.provider_status ?? null,
      };
      setAccount(stand_in);
      setStatus("signed-in");
      return stand_in;
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Signing out locally is what the person asked for. A server that cannot
      // be reached must not leave them apparently still signed in.
    }
    setAuthToken(null);
    setAccount(null);
    setStatus("signed-out");
    setExpired(false);
  }, []);

  const value = useMemo<AuthValue>(() => ({
    status,
    account,
    role: account?.role ?? null,
    ready: status !== "loading",
    expired,
    accept,
    signOut,
    refresh: () => load(),
    clearExpired: () => setExpired(false),
  }), [status, account, expired, accept, signOut, load]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
