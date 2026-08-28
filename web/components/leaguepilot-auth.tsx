"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, CheckCircle2, Eye, EyeOff, Loader2, LockKeyhole, Mail, ShieldCheck, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Mode = "signin" | "register" | "forgot";

const content = {
  signin: {
    eyebrow: "WELCOME BACK",
    title: "Your league is waiting.",
    copy: "Sign in to review this week’s decisions, reports, and live analysis jobs.",
  },
  register: {
    eyebrow: "CREATE YOUR COMMAND CENTER",
    title: "Build your weekly edge.",
    copy: "Create one account for the web dashboard and future mobile experience.",
  },
  forgot: {
    eyebrow: "ACCOUNT RECOVERY",
    title: "Get back in the game.",
    copy: "Enter the email on your account. We’ll be honest if recovery email is not configured yet.",
  },
};

export function LeaguePilotAuth({ mode }: { mode: Mode }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    if (!email.trim()) {
      setMessage({ tone: "error", text: "Enter your email address." });
      return;
    }
    if (mode !== "forgot" && !password) {
      setMessage({ tone: "error", text: "Enter your password." });
      return;
    }
    if (mode === "register" && (!name.trim() || password !== confirm)) {
      setMessage({ tone: "error", text: !name.trim() ? "Enter your name." : "The passwords do not match." });
      return;
    }

    setLoading(true);
    const endpoint = mode === "signin" ? "/api/auth/login" : mode === "register" ? "/api/auth/register" : "/api/auth/forgot-password";
    const payload = mode === "signin"
      ? { email, password }
      : mode === "register"
        ? { name, email, password, passwordConfirm: confirm }
        : { email };

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.message || "Something went wrong. Please try again.");
      if (mode === "forgot") {
        setMessage({ tone: "success", text: result.message });
      } else {
        window.location.assign("/app");
      }
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Something went wrong." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="lp-auth-page">
      <div className="lp-auth-field" aria-hidden="true" />
      <Link href="/" className="lp-auth-back"><ArrowLeft /> Back to homepage</Link>
      <section className="lp-auth-story">
        <Link href="/" className="lp-app-logo" aria-label="LEAGUEPILOT AI homepage">
          <span>LP<small>AI</small></span><b>LEAGUEPILOT <em>AI</em></b>
        </Link>
        <div>
          <p className="lp-auth-kicker">YOUR LEAGUE. ONE OPERATING SYSTEM.</p>
          <h1>Less digging.<br/><em>More winning.</em></h1>
          <p>Lineup intelligence, waiver plans, realistic trade matches, weekly reports, and league activity—organized around your real ESPN league.</p>
        </div>
        <div className="lp-auth-trust">
          <span><ShieldCheck /> Human approval stays on</span>
          <span><LockKeyhole /> Credentials stay server-side</span>
          <span><CheckCircle2 /> No silent ESPN changes</span>
        </div>
      </section>

      <section className="lp-auth-panel">
        <div className="lp-auth-card">
          <div className="lp-auth-icon">{mode === "register" ? <UserPlus /> : mode === "forgot" ? <Mail /> : <LockKeyhole />}</div>
          <p className="lp-auth-kicker">{content[mode].eyebrow}</p>
          <h2>{content[mode].title}</h2>
          <p className="lp-auth-copy">{content[mode].copy}</p>

          <form onSubmit={submit} noValidate>
            {mode === "register" && <label><span>Full name</span><Input autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" /></label>}
            <label><span>Email address</span><Input type="email" inputMode="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label>
            {mode !== "forgot" && <label><span>Password</span><div className="lp-password-field"><Input type={showPassword ? "text" : "password"} autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" /><button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff /> : <Eye />}</button></div></label>}
            {mode === "register" && <label><span>Confirm password</span><Input type={showPassword ? "text" : "password"} autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} placeholder="Repeat your password" /></label>}

            {message && <div className={`lp-auth-message ${message.tone}`} role="status">{message.tone === "success" ? <CheckCircle2 /> : <ShieldCheck />}<span>{message.text}</span></div>}

            <Button type="submit" className="lp-auth-submit" disabled={loading}>
              {loading ? <><Loader2 className="lp-spin" /> Working…</> : <>{mode === "signin" ? "Sign In" : mode === "register" ? "Create Account" : "Send Recovery Link"}<ArrowRight /></>}
            </Button>
          </form>

          <div className="lp-auth-links">
            {mode === "signin" && <><a href="/forgot-password">Forgot password?</a><p>New to LEAGUEPILOT? <a href="/create-account">Create account</a></p></>}
            {mode === "register" && <p>Already have an account? <a href="/sign-in">Sign in</a></p>}
            {mode === "forgot" && <p>Remembered your password? <a href="/sign-in">Back to sign in</a></p>}
          </div>
          <p className="lp-auth-backend"><span /> Connected to the shared PocketBase backend</p>
        </div>
      </section>
    </main>
  );
}
