import type { Metadata } from "next";
import { Archivo, Metal_Mania } from "next/font/google";
import SettingsLink from "@/components/SettingsLink";
import "./globals.css";

// Archivo rather than Next's default Geist: a grotesque with a bit of
// gig-poster grit that sits alongside Metal Mania instead of reading generic.
const archivo = Archivo({
  variable: "--font-archivo",
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
      className={`${archivo.variable} ${metalMania.variable} antialiased`}
    >
      <body className="flex min-h-dvh flex-col bg-[var(--color-bg)] font-sans">
        <SettingsLink />
        <div className="flex min-h-dvh flex-1 flex-col">{children}</div>
      </body>
    </html>
  );
}
