"use client";

import { useState } from "react";

import { ApiError, authApi } from "@/lib/api";
import type { Account } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";

/**
 * Signing in, or creating a customer account.
 *
 * The same panel serves the /login page and the review step of a booking. That
 * is the reason it is a component rather than a page: somebody who has picked a
 * provider and a time and is then sent away to a sign-in page comes back to
 * nothing, having lost the two decisions that were the hard part. Here they
 * sign in where they stand and the booking carries on.
 *
 * Provider *registration* is not here. It asks for a business, an address and a
 * list of services, which is a page rather than a panel; this handles provider
 * sign-in only, because that half really is just an email and a password.
 */

type Mode = "sign-in" | "register";

interface AuthPanelProps {
  /** Which kind of account this panel is for. Registration is offered only to
   *  customers; a provider is pointed at their own form instead. */
  audience?: "customer" | "provider";
  initialMode?: Mode;
  onDone: (account: Account | null) => void;
  /** Shown above the form when the reason for signing in is not obvious, e.g.
   *  "Almost there. Sign in and we will confirm your appointment." */
  intro?: string;
}

export function AuthPanel({
  audience = "customer",
  initialMode = "sign-in",
  onDone,
  intro,
}: AuthPanelProps) {
  const { accept } = useAuth();
  const [mode, setMode] = useState<Mode>(audience === "provider" ? "sign-in" : initialMode);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState("");
  const [busy, setBusy] = useState(false);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!email.trim()) errs.email = "Your email address is needed";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = "That does not look like an email address";
    if (!password) errs.password = "Your password is needed";
    // The server requires eight characters. Saying so before the request saves
    // somebody a round trip to be told off.
    else if (mode === "register" && password.length < 8)
      errs.password = "Please use at least eight characters";
    if (mode === "register" && !name.trim()) errs.name = "Your name is needed";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || !validate()) return;

    setBusy(true);
    setFailure("");
    try {
      const token =
        mode === "sign-in"
          ? await authApi.login(email.trim(), password)
          : await authApi.registerCustomer({
              name: name.trim(),
              email: email.trim(),
              password,
              phone: phone.trim() || undefined,
              address: address.trim() || undefined,
            });

      const account = await accept(token);
      onDone(account);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          // The server counted too many failures. Say what to do, not just
          // that it refused.
          setFailure("Too many attempts. Please wait a few minutes and try again.");
        } else if (err.status === 409) {
          setFailure("There is already an account with that email. Try signing in instead.");
        } else if (err.status === 401) {
          setFailure("Those details do not match an account.");
        } else {
          setFailure(err.detail);
        }
      } else {
        setFailure("We could not reach the server. Please check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3.5">
      {intro && <p className="text-sm leading-relaxed text-ink-muted">{intro}</p>}

      {mode === "register" && (
        <Field
          label="Your name"
          value={name}
          onChange={setName}
          error={errors.name}
          required
          autoComplete="name"
          placeholder="Alex Morgan"
        />
      )}

      <Field
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        error={errors.email}
        required
        autoComplete="email"
        placeholder="you@example.com"
      />

      <Field
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        error={errors.password}
        required
        autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
        hint={mode === "register" ? "At least eight characters." : undefined}
      />

      {mode === "register" && (
        <>
          <Field
            label="Phone"
            type="tel"
            value={phone}
            onChange={setPhone}
            autoComplete="tel"
            hint="So the provider can reach you about the visit."
          />
          <Field
            label="Address"
            value={address}
            onChange={setAddress}
            autoComplete="street-address"
            hint="Where the work is. You can change it for any one booking."
          />
        </>
      )}

      {failure && (
        <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {failure}
        </p>
      )}

      <Button type="submit" disabled={busy} className="w-full" size="lg">
        {busy
          ? mode === "sign-in" ? "Signing in…" : "Creating your account…"
          : mode === "sign-in" ? "Sign in" : "Create account"}
      </Button>

      {audience === "customer" ? (
        <p className="text-center text-sm text-ink-muted">
          {mode === "sign-in" ? "No account yet?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "sign-in" ? "register" : "sign-in");
              setErrors({});
              setFailure("");
            }}
            className="font-semibold text-brand-600 hover:underline"
          >
            {mode === "sign-in" ? "Create one" : "Sign in"}
          </button>
        </p>
      ) : (
        <p className="text-center text-sm text-ink-muted">
          Not registered as a provider yet?{" "}
          <a href="/provider/register" className="font-semibold text-brand-600 hover:underline">
            Apply to join
          </a>
        </p>
      )}
    </form>
  );
}
