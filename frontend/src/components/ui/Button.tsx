import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
}

/**
 * Sizes are heights rather than vertical padding, so a button lines up with an
 * input of the same size. `lg` was `py-4 text-lg`, which made a 60px button
 * with 18px text: fine alone, oversized next to anything else.
 */
const variantClasses = {
  primary: "bg-brand-500 hover:bg-brand-600 text-white",
  secondary: "bg-surface hover:bg-surface-hover text-ink border border-line",
  ghost: "hover:bg-surface-hover text-ink",
  outline: "border border-brand-300 text-brand-700 hover:bg-brand-50",
};

const sizeClasses = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-control font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
);
Button.displayName = "Button";
