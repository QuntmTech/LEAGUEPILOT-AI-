import type { Metadata } from "next";
import { LeaguePilotAuth } from "@/components/leaguepilot-auth";

export const metadata: Metadata = { title: "Sign In — LEAGUEPILOT AI" };

export default function SignInPage() {
  return <LeaguePilotAuth mode="signin" />;
}
