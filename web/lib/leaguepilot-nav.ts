import {
  Activity,
  BellRing,
  FileText,
  LayoutDashboard,
  ListChecks,
  Settings,
  Trophy,
  Handshake,
} from "lucide-react";

/** The authenticated application's sections, shared by the sidebar and mobile nav. */
export const NAV_SECTIONS = [
  { id: "overview", label: "Overview", short: "Overview", icon: LayoutDashboard },
  { id: "moves", label: "Moves", short: "Moves", icon: ListChecks },
  { id: "trades", label: "Trade Lab", short: "Trades", icon: Handshake },
  { id: "league", label: "League Intelligence", short: "League", icon: Trophy },
  { id: "alerts", label: "Alerts", short: "Alerts", icon: BellRing },
  { id: "reports", label: "Reports", short: "Reports", icon: FileText },
  { id: "activity", label: "Activity", short: "Activity", icon: Activity },
  { id: "settings", label: "Settings", short: "Settings", icon: Settings },
] as const;

export type SectionId = (typeof NAV_SECTIONS)[number]["id"];

export function isSectionId(value: string): value is SectionId {
  return NAV_SECTIONS.some((section) => section.id === value);
}
