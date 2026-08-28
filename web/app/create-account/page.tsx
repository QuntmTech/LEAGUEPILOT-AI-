import type { Metadata } from "next";
import { LeaguePilotAuth } from "@/components/leaguepilot-auth";

export const metadata: Metadata = { title: "Create Account — LEAGUEPILOT AI" };

export default function CreateAccountPage() {
  return <LeaguePilotAuth mode="register" />;
}
