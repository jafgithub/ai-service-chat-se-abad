import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Service Assistant — Find it. Book it. Done.",
  description:
    "Chat or speak to our AI to find products, get pricing, and place your order in minutes.",
  keywords: ["AI ordering", "smart market", "food ordering", "voice ordering"],
  openGraph: {
    title: "Service Assistant — Find it. Book it. Done.",
    description: "AI-powered ordering assistant for meat, dairy, and more.",
    type: "website",
  },
};

/**
 * `viewportFit: "cover"` is what makes `env(safe-area-inset-*)` report real
 * values on notched phones; without it those insets are always 0 and the
 * checkout sheet's bottom padding would do nothing. `interactiveWidget` keeps
 * the on-screen keyboard from covering the checkout buttons: it shrinks the
 * viewport instead of drawing over it, so `dvh` accounts for the keyboard too.
 */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full scroll-smooth antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
