import type { Metadata } from "next";
import { Suspense } from "react";
import { AppProviders } from "@/providers/app-providers";
import { Geist, Geist_Mono } from "next/font/google";
import { THEME_INIT_SCRIPT } from "@/components/ui/themeScript";
import "katex/dist/katex.min.css";
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
  title: "Stellaris",
  description: "An experiment studio for questions, evidence, and results.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable}`}
      // The theme script sets data-theme before hydration.
      suppressHydrationWarning
    >
      <head><script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} /></head>
      <body><Suspense fallback={<p>Opening Stellaris…</p>}><AppProviders>{children}</AppProviders></Suspense></body>
    </html>
  );
}
