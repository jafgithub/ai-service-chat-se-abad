"use client";

import { cn } from "@/lib/utils";

/**
 * A labelled input, the same one everywhere.
 *
 * The forms in this application are the sign-up, the sign-in and the provider's
 * own details, and before this each of them spelled out the same label, border
 * and error markup by hand. That is how the error styling drifted: one form
 * turned the border red, another only printed text under it.
 */

interface FieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  disabled?: boolean;
  autoComplete?: string;
  min?: string;
  step?: string;
  /** Rendered as a textarea instead, for descriptions and notes. */
  rows?: number;
  className?: string;
}

export function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  error,
  hint,
  required,
  disabled,
  autoComplete,
  min,
  step,
  rows,
  className,
}: FieldProps) {
  const id = `f-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  const shared = cn(
    "w-full rounded-control border bg-surface px-3 text-sm text-ink placeholder-ink-faint transition-colors",
    "focus:border-brand-300 focus:outline-none disabled:bg-surface-sunken disabled:text-ink-muted",
    error ? "border-danger" : "border-line",
  );

  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-xs font-semibold text-ink">
        {label}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>

      {rows ? (
        <textarea
          id={id}
          value={value}
          rows={rows}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          className={cn(shared, "py-2.5 leading-relaxed")}
        />
      ) : (
        <input
          id={id}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete={autoComplete}
          min={min}
          step={step}
          aria-invalid={Boolean(error)}
          className={cn(shared, "h-11")}
        />
      )}

      {error ? (
        <p className="mt-1 text-xs font-medium text-danger">{error}</p>
      ) : hint ? (
        <p className="mt-1 text-xs text-ink-muted">{hint}</p>
      ) : null}
    </div>
  );
}
