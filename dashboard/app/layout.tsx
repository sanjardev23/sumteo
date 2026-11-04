import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex" });

export const metadata: Metadata = {
  title: "숨터 Sumteo",
  description: "AI crowd-safety early warning — control room and on-site views",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={`h-full antialiased ${plex.variable}`}>
      <body className="min-h-full bg-[#F4F6F9] text-[#1B2430]">{children}</body>
    </html>
  );
}
