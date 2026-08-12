"use client";

import { useState } from "react";

import { ApiError, providerMeApi } from "@/lib/api";
import type { ProviderProfile } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { ProviderShell } from "@/components/provider/ProviderShell";
import { Failed, Loading } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";

/**
 * The details customers see.
 *
 * `status` is not on this form, and the omission is the point: a provider who
 * could set their own status to active would make approval decorative. The API
 * refuses it too, so this is agreement rather than the only line of defence.
 */
export default function ProviderProfilePage() {
  const { status, account, refresh } = useAuth();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [failure, setFailure] = useState("");

  const { data: loaded, error, loading, reload } = useResource(
    (signal) => providerMeApi.profile(signal),
    [],
    { enabled: status === "signed-in" && account?.role === "provider" }
  );

  // What has been typed since it loaded. Null means nothing has been touched,
  // so the fetched values are shown as they are; this is what lets a reload
  // after saving take effect without discarding an edit in progress.
  const [edits, setEdits] = useState<Partial<ProviderProfile> | null>(null);
  const profile = loaded ? { ...loaded, ...edits } : null;

  const set = (key: keyof ProviderProfile) => (value: string) =>
    setEdits((prev) => ({ ...prev, [key]: value }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile || saving) return;

    setSaving(true);
    setFailure("");
    setSaved(false);
    try {
      await providerMeApi.saveProfile({
        business_name: profile.business_name,
        contact_name: profile.contact_name,
        phone: profile.phone,
        website: profile.website,
        description: profile.description,
        address: profile.address,
        city: profile.city,
        postcode: profile.postcode,
      });
      setSaved(true);
      setEdits(null);
      // The name in the header comes from the account, so it has to be told.
      void refresh();
      reload();
    } catch (err) {
      setFailure(err instanceof ApiError ? err.detail : "We could not save that just now.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <ProviderShell title="My business" subtitle="What customers see when they look you up.">
      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || !profile ? (
        <Loading label="Loading your details" />
      ) : (
        <form onSubmit={save} className="max-w-xl space-y-3.5 rounded-card border border-line bg-surface p-5 shadow-card">
          <Field label="Business name" value={profile.business_name} onChange={set("business_name")} required />
          <Field label="Your name" value={profile.contact_name ?? ""} onChange={set("contact_name")} />

          {/* Read only, because it identifies the account. Changing it would
              mean changing what you sign in with, which is a different and much
              more careful operation than editing a profile. */}
          <Field
            label="Email"
            value={profile.email ?? ""}
            onChange={() => {}}
            disabled
            hint="This is what you sign in with. Get in touch if it needs to change."
          />

          <Field label="Phone" type="tel" value={profile.phone ?? ""} onChange={set("phone")} />
          <Field label="Website" value={profile.website ?? ""} onChange={set("website")} placeholder="https://" />
          <Field
            label="About your business"
            value={profile.description ?? ""}
            onChange={set("description")}
            rows={5}
            hint="Shown on your public profile."
          />

          <Field label="Address" value={profile.address ?? ""} onChange={set("address")} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Town or city" value={profile.city ?? ""} onChange={set("city")} />
            <Field label="Postcode" value={profile.postcode ?? ""} onChange={set("postcode")} />
          </div>

          {failure && (
            <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
              {failure}
            </p>
          )}
          {saved && (
            <p role="status" className="rounded-control border border-positive/30 bg-positive-soft px-3 py-2 text-sm text-positive">
              Saved.
            </p>
          )}

          <Button type="submit" disabled={saving} size="lg">
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </form>
      )}
    </ProviderShell>
  );
}
