"use client";

import { useState } from "react";
import { getServiceEmoji } from "@/lib/serviceIcon";
import { cn } from "@/lib/utils";

/**
 * A service photo that degrades to an icon for what the work is.
 *
 * The old cards tested `image_url?.startsWith("http")` and showed an emoji when
 * it failed. Since the API started serving every product a stable
 * `/api/v1/media/{id}` URL that test is always true, so the fallback became
 * dead code — and roughly 40% of those URLs 404 (13 of 30 sampled on a
 * "chicken" search), leaving the browser's broken-image glyph on the card.
 *
 * The fix has to be `onError`, because a 404 is only discoverable at load time.
 */

interface ServiceImageProps {
  src: string | null | undefined;
  alt: string;
  /** Used to pick the fallback icon. */
  category?: string | null;
  className?: string;
  /** Tailwind text size for the fallback glyph, e.g. "text-5xl". */
  iconClassName?: string;
  /** Above-the-fold images should not be lazy. */
  priority?: boolean;
  /**
   * `contain` by default, so nothing is cropped away. `cover` is still right
   * for a wide banner.
   */
  fit?: "contain" | "cover";
}

export function ServiceImage({
  src,
  alt,
  category,
  className,
  iconClassName = "text-4xl",
  priority = false,
  fit = "contain",
}: ServiceImageProps) {
  const [failed, setFailed] = useState(false);
  const usable = !!src && /^https?:\/\//.test(src) && !failed;

  if (!usable) {
    return (
      <div
        className={cn(
          "flex h-full w-full items-center justify-center bg-brand-50 select-none",
          className
        )}
        role="img"
        aria-label={alt}
      >
        {/* The name is the better signal: a lot of work is filed under a broad
            heading, but "Emergency pipe leak repair" says what it is whichever
            heading it sits under. Both are searched, category first. */}
        <span className={iconClassName} aria-hidden>
          {getServiceEmoji(`${category || ""} ${alt}`)}
        </span>
      </div>
    );
  }

  return (
    // A plain <img>: static export plus an arbitrary upstream CDN host.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src as string}
      alt={alt}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      onError={() => setFailed(true)}
      className={cn(
        "h-full w-full",
        fit === "cover" ? "object-cover" : "object-contain",
        className
      )}
    />
  );
}
