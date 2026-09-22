import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Health & Supply Chain Command Center",
  description: "Track 3 — Smart Health & Supply Chain Resilience national platform",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className="h-full antialiased dark"
    >
      <body className="min-h-full flex flex-col bg-slate-950">{children}</body>
    </html>
  );
}
