import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/auth/AuthProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Service Assistant — Describe it. Book it. Done.",
  description:
    "Describe what has gone wrong and the assistant finds the service, shows you who does it and what they charge, and books a time.",
  keywords: ["book a plumber", "find a tradesperson", "service booking", "appointments"],
  openGraph: {
    title: "Service Assistant — Describe it. Book it. Done.",
    description:
      "Find a service, compare providers, and book an appointment by chat or by voice.",
    type: "website",
  },
};

/**
 * `viewportFit: "cover"` is what makes `env(safe-area-inset-*)` report real
 * values on notched phones; without it those insets are always 0 and the
 * booking sheet's bottom padding would do nothing. `interactiveWidget` keeps
 * the on-screen keyboard from covering the confirm button: it shrinks the
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
      <body className="min-h-full flex flex-col">
        {/* Wraps everything, because who is signed in decides what the header
            shows on every page, and because the token has to be picked up once
            rather than by each page separately. */}
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
