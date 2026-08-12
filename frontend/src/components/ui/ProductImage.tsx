"use client";

import { useState } from "react";
import { getCategoryEmoji } from "@/lib/productEmoji";
import { cn } from "@/lib/utils";

/**
 * A product photo that degrades to a category icon.
 *
 * The old cards tested `image_url?.startsWith("http")` and showed an emoji when
 * it failed. Since the API started serving every product a stable
 * `/api/v1/media/{id}` URL that test is always true, so the fallback became
 * dead code — and roughly 40% of those URLs 404 (13 of 30 sampled on a
 * "chicken" search), leaving the browser's broken-image glyph on the card.
 *
 * The fix has to be `onError`, because a 404 is only discoverable at load time.
 */

interface ProductImageProps {
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
   * `contain` by default. These are packshots: a carton or a bottle photographed
   * upright on white. `cover` fills the box but slices the top and bottom off the
   * packaging, so the shopper sees a band of the middle of a label and cannot
   * tell one product from another. `cover` is still right for a wide banner.
   */
  fit?: "contain" | "cover";
}

export function ProductImage({
  src,
  alt,
  category,
  className,
  iconClassName = "text-4xl",
  priority = false,
  fit = "contain",
}: ProductImageProps) {
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
        {/* The name is a better signal than the category: the catalog files a
            lot of products under "General", but "Friendly Farms Whole Milk"
            still matches on "milk". Both are searched, category first. */}
        <span className={iconClassName} aria-hidden>
          {getCategoryEmoji(`${category || ""} ${alt}`)}
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
