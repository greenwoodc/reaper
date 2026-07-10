import type { Metadata } from "next";
import { Geist, Metal_Mania } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const metalMania = Metal_Mania({
  variable: "--font-metal-mania",
  weight: "400",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Reaper",
  description: "Scan, download, and playlist your Navidrome library from Exportify CSVs.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${metalMania.variable} antialiased`}
    >
      <body className="flex min-h-dvh flex-col bg-[var(--color-bg)] font-sans">
        <Link
          href="/settings"
          className="fixed right-4 top-4 z-10 text-xs text-[var(--color-muted)] transition-colors hover:text-[var(--color-accent)]"
        >
          ⚙ Settings
        </Link>
        <div className="flex min-h-dvh flex-1 flex-col">{children}</div>
      </body>
    </html>
  );
}
