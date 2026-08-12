"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

import { BRAND_NAME } from "@/constants";
import { Button } from "@/components/ui/Button";
import { AccountMenu } from "@/components/layout/AccountMenu";
import { cn } from "@/lib/utils";

interface NavbarProps {
  onStart: () => void;
}

const NAV_LINKS = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Services", href: "#services" },
  { label: "Contact", href: "#footer" },
];

export function Navbar({ onStart }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleNavClick = (href: string) => {
    setMenuOpen(false);
    document.querySelector(href)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <header
      className={cn(
        "fixed top-0 inset-x-0 z-40 transition-all duration-300",
        scrolled
          ? "bg-surface/90 backdrop-blur-md shadow-sm border-b border-line"
          : "bg-transparent"
      )}
    >
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <a
          href="#hero"
          onClick={(e) => { e.preventDefault(); handleNavClick("#hero"); }}
          className="flex items-center gap-2 font-extrabold text-xl text-ink"
        >
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-rose-500 flex items-center justify-center text-white text-base">
            📅
          </span>
          {BRAND_NAME}
        </a>

        <div className="hidden md:flex items-center gap-6">
          {NAV_LINKS.map((link) => (
            <button
              key={link.href}
              onClick={() => handleNavClick(link.href)}
              className="text-sm font-medium text-ink-muted hover:text-brand-500 transition-colors"
            >
              {link.label}
            </button>
          ))}
          {/* The provider's way in. It has to be visible from the front page:
              a marketplace with no obvious door for the people who do the work
              only ever fills up one side. */}
          <Link
            href="/provider/register"
            className="text-sm font-medium text-brand-600 hover:text-orange-700 border border-brand-300 hover:border-orange-500 rounded-full px-4 py-1.5 transition-colors"
          >
            Service provider
          </Link>
          <Button size="sm" onClick={onStart}>
            Find a service
          </Button>
          <AccountMenu />
        </div>

        <button
          className="md:hidden w-9 h-9 flex flex-col items-center justify-center gap-1.5"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          <span className={cn("w-5 h-0.5 bg-gray-700 transition-all", menuOpen && "rotate-45 translate-y-2")} />
          <span className={cn("w-5 h-0.5 bg-gray-700 transition-all", menuOpen && "opacity-0")} />
          <span className={cn("w-5 h-0.5 bg-gray-700 transition-all", menuOpen && "-rotate-45 -translate-y-2")} />
        </button>
      </nav>

      {menuOpen && (
        <div className="md:hidden bg-surface border-t border-line px-4 py-4 flex flex-col gap-3 shadow-lg">
          {NAV_LINKS.map((link) => (
            <button
              key={link.href}
              onClick={() => handleNavClick(link.href)}
              className="text-left text-base font-medium text-ink-muted hover:text-brand-500 py-1"
            >
              {link.label}
            </button>
          ))}
          <Link
            href="/provider/register"
            onClick={() => setMenuOpen(false)}
            className="text-left text-base font-medium text-brand-600 hover:text-orange-700 py-1"
          >
            Service provider
          </Link>
          <Link
            href="/login"
            onClick={() => setMenuOpen(false)}
            className="text-left text-base font-medium text-ink-muted hover:text-brand-500 py-1"
          >
            Sign in
          </Link>
          <Button size="sm" onClick={() => { setMenuOpen(false); onStart(); }} className="mt-2">
            Find a service
          </Button>
        </div>
      )}
    </header>
  );
}
