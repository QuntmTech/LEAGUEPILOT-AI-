import type { Metadata } from "next";
import { LeaguePilotAuth } from "@/components/leaguepilot-auth";

export const metadata: Metadata = { title: "Forgot Password — LEAGUEPILOT AI" };

export default function ForgotPasswordPage() {
  return <LeaguePilotAuth mode="forgot" />;
}
