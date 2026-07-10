import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const plusJakartaSans = localFont({
  src: [
    { path: "../public/fonts/PlusJakartaSans-300.woff2", weight: "300", style: "normal" },
    { path: "../public/fonts/PlusJakartaSans-400.woff2", weight: "400", style: "normal" },
    { path: "../public/fonts/PlusJakartaSans-500.woff2", weight: "500", style: "normal" },
    { path: "../public/fonts/PlusJakartaSans-600.woff2", weight: "600", style: "normal" },
    { path: "../public/fonts/PlusJakartaSans-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-plus-jakarta-sans",
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
});

const geistMono = localFont({
  src: [
    { path: "../public/fonts/GeistMono-Regular.woff2", weight: "400", style: "normal" },
    { path: "../public/fonts/GeistMono-500.woff2", weight: "500", style: "normal" },
    { path: "../public/fonts/GeistMono-600.woff2", weight: "600", style: "normal" },
    { path: "../public/fonts/GeistMono-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-geist-mono",
  display: "swap",
  fallback: ["ui-monospace", "SFMono-Regular", "monospace"],
});

const playfairDisplay = localFont({
  src: [
    { path: "../public/fonts/PlayfairDisplay-400.woff2", weight: "400", style: "normal" },
    { path: "../public/fonts/PlayfairDisplay-500.woff2", weight: "500", style: "normal" },
    { path: "../public/fonts/PlayfairDisplay-600.woff2", weight: "600", style: "normal" },
    { path: "../public/fonts/PlayfairDisplay-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-playfair-display",
  display: "swap",
  fallback: ["Georgia", "Times New Roman", "serif"],
});

export const metadata: Metadata = {
  title: "CulturalBridge",
  description: "AI-powered cultural adaptation translation system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`h-full antialiased ${plusJakartaSans.variable} ${geistMono.variable} ${playfairDisplay.variable}`}
    >
      <body className="min-h-full flex-col flex font-sans">{children}</body>
    </html>
  );
}
