import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "숨터 Sumteo",
  description: "AI crowd-safety early warning — control room and on-site views",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full bg-zinc-950 text-zinc-100">{children}</body>
    </html>
  );
}
