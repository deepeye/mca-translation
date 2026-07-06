import type { Metadata } from "next";
import "./globals.css";

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
      className="h-full antialiased"
      style={{
        "--font-plus-jakarta-sans":
          '"Plus Jakarta Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        "--font-geist-mono":
          '"Geist Mono", ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
        "--font-playfair-display":
          '"Playfair Display", Georgia, "Times New Roman", serif',
      } as React.CSSProperties}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
