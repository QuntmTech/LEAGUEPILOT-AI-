import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./platform.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#102e27",
};

export const metadata: Metadata = {
  title: "LEAGUEPILOT AI — Intelligent Fantasy Football Automation",
  description:
    "Turn your ESPN fantasy league into an intelligent weekly command center with lineup optimization, waiver plans, trade matching, power rankings, automated reports, and human-controlled decisions.",
  openGraph: {
    title: "LEAGUEPILOT AI — Intelligent Fantasy Football Automation",
    description:
      "Lineup intelligence, waiver plans, realistic trade matches, power rankings, scheduled reports, and human-controlled decisions for ESPN fantasy football.",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "LEAGUEPILOT AI — Intelligent Fantasy Football Automation",
    description:
      "Put your ESPN fantasy league under intelligent control—without giving up control of your team.",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
