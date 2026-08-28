import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LeaguePilotDashboard } from "@/components/leaguepilot-dashboard";
import { LEAGUEPILOT_AUTH_COOKIE } from "@/lib/leaguepilot-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Command Center — LEAGUEPILOT AI",
  description: "Your authenticated LEAGUEPILOT AI fantasy football command center.",
};

export default async function AppPage() {
  const token = (await cookies()).get(LEAGUEPILOT_AUTH_COOKIE)?.value;
  if (!token) redirect("/sign-in");
  return <LeaguePilotDashboard />;
}
