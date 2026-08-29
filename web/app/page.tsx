"use client";

import { useState } from "react";
import {
  Activity, ArrowRight, BarChart3, Bot, CalendarClock, Check, ChevronRight,
  CircleAlert, ClipboardCheck, Clock3, FileCheck2, Gauge, LineChart, ListChecks,
  LockKeyhole, Menu, MessageSquareText, Radar, RefreshCw, SearchCheck, Send,
  ShieldCheck, Sparkles, Target, TrendingUp, Trophy, Users, WandSparkles, X, Zap,
} from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type BetaData = { name: string; email: string; role: string; leagues: string; platform: string; wish: string };

const features = [
  { icon: ListChecks, title: "Lineup Lab", eyebrow: "Start/sit intelligence", copy: "See the move, projected improvement, injury risk, confidence, and supporting evidence before you change anything.", tone: "lime" },
  { icon: Radar, title: "Waiver Radar", eyebrow: "Roster-specific upgrades", copy: "Stop collecting generic waiver lists. Find real available players that improve your exact team.", tone: "paper" },
  { icon: RefreshCw, title: "Trade Finder", eyebrow: "Mutual roster fit", copy: "Find trades that help your roster and still give the other manager a reason to answer.", tone: "forest" },
  { icon: Trophy, title: "League Pulse", eyebrow: "A league worth talking about", copy: "Power rankings, close-game summaries, weekly recaps, and group-chat-ready storylines.", tone: "gold" },
  { icon: CalendarClock, title: "Automation Control", eyebrow: "The weekly grind, scheduled", copy: "Schedule analysis and reports while keeping every roster decision under your control.", tone: "paper" },
  { icon: SearchCheck, title: "Evidence & Data Quality", eyebrow: "Confidence with receipts", copy: "Know the source, freshness, missing information, and risk behind every recommendation.", tone: "blue" },
];

const workflow = [
  { id: "connect", n: "01", label: "Connect", title: "Bring in your ESPN league.", copy: "Connect a public or private ESPN Fantasy Football league. Private session credentials are encrypted before database storage.", icon: LockKeyhole },
  { id: "sync", n: "02", label: "Synchronize", title: "One reliable league snapshot.", copy: "Normalize rosters, projections, matchups, free agents, injuries, scoring settings, and lineup eligibility.", icon: RefreshCw },
  { id: "analyze", n: "03", label: "Analyze", title: "Run the weekly intelligence cycle.", copy: "Deterministic lineup, waiver, trade, and league-wide analysis turns the snapshot into prioritized opportunities.", icon: Activity },
  { id: "approve", n: "04", label: "Approve", title: "You stay in control.", copy: "Review impact, confidence, evidence, and risk flags. Nothing silently changes in ESPN.", icon: ClipboardCheck },
  { id: "share", n: "05", label: "Share", title: "Make the league feel alive.", copy: "Create a recap or send selected updates to a Discord or GroupMe channel you explicitly configure.", icon: Send },
];

const faqs = [
  ["Does LEAGUEPILOT AI automatically change my ESPN team?", "No. It analyzes and queues recommendations, but the current product does not submit lineup, waiver, or trade actions to ESPN."],
  ["Does it work with private ESPN leagues?", "Yes. Private leagues can connect using ESPN session credentials, which are encrypted before database storage and never returned through the application API."],
  ["Is a paid AI model required?", "No. The deterministic rules narrator works without a paid AI model. Optional model providers can improve narrative presentation."],
  ["What happens if the AI provider fails?", "LEAGUEPILOT AI falls back to deterministic narration using the same verified league facts."],
  ["Does it support Yahoo or Sleeper?", "The initial product is ESPN-first. Yahoo and Sleeper are potential future integrations—not current features."],
  ["Is this a betting or DFS product?", "No. It is a season-long fantasy-league intelligence and engagement platform."],
  ["Is it affiliated with ESPN?", "No. LEAGUEPILOT AI is not affiliated with, endorsed by, or sponsored by ESPN or The Walt Disney Company."],
  ["How much does it cost?", "The Founder Beta will help validate packaging and pricing. No invented public price is being advertised today."],
];

function Logo({ light = false }: { light?: boolean }) {
  return <a href="#top" className={`logo ${light ? "light" : ""}`} aria-label="LEAGUEPILOT AI home">
    <span className="logo-mark"><i>LP</i><b>AI</b></span><span className="logo-type">LEAGUEPILOT <b>AI</b></span>
  </a>;
}

function BetaForm({ data, setData, compact = false }: { data: BetaData; setData: (v: BetaData) => void; compact?: boolean }) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const update = (key: keyof BetaData, value: string) => {
    setData({ ...data, [key]: value });
    if (errors[key]) setErrors({ ...errors, [key]: "" });
  };
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!data.name.trim()) next.name = "First name is required.";
    if (!/^\S+@\S+\.\S+$/.test(data.email)) next.email = "Enter a valid email.";
    if (!data.role) next.role = "Choose your fantasy role.";
    if (!data.leagues || Number(data.leagues) < 1) next.leagues = "Enter at least one league.";
    if (!data.platform) next.platform = "Choose a platform.";
    setErrors(next);
    if (Object.keys(next).length) return;
    setLoading(true);
    // Production integration point: replace this preview delay with the beta signup endpoint.
    await new Promise((resolve) => setTimeout(resolve, 850));
    setLoading(false); setSent(true);
  }
  if (sent) return <div className="form-success" role="status">
    <span><Check /></span><p className="kicker">FOUNDER BETA INTEREST RECEIVED</p>
    <h3>You’re cleared for the next drive, {data.name.split(" ")[0]}.</h3>
    <p>The complete confirmation flow is working. Production delivery connects at the isolated signup endpoint.</p>
    <Button type="button" variant="outline" onClick={() => setSent(false)}>Review my details</Button>
  </div>;
  const error = (key: string) => errors[key] && <small className="field-error">{errors[key]}</small>;
  return <form className={`beta-form ${compact ? "compact" : ""}`} onSubmit={submit} noValidate>
    <div className="field-grid">
      <label><span>First name</span><Input value={data.name} onChange={e => update("name", e.target.value)} placeholder="Colton" aria-invalid={!!errors.name}/>{error("name")}</label>
      <label><span>Email address</span><Input type="email" value={data.email} onChange={e => update("email", e.target.value)} placeholder="you@example.com" aria-invalid={!!errors.email}/>{error("email")}</label>
      <label><span>Fantasy role</span><Select value={data.role} onValueChange={v => update("role", v)}><SelectTrigger className="form-select" aria-invalid={!!errors.role}><SelectValue placeholder="Choose a role"/></SelectTrigger><SelectContent><SelectItem value="Manager">Manager</SelectItem><SelectItem value="Commissioner">Commissioner</SelectItem><SelectItem value="Both">Both</SelectItem></SelectContent></Select>{error("role")}</label>
      <label><span>Number of leagues</span><Input type="number" min="1" max="50" value={data.leagues} onChange={e => update("leagues", e.target.value)} placeholder="2" aria-invalid={!!errors.leagues}/>{error("leagues")}</label>
      <label className="wide"><span>Primary platform</span><Select value={data.platform} onValueChange={v => update("platform", v)}><SelectTrigger className="form-select" aria-invalid={!!errors.platform}><SelectValue placeholder="Choose a platform"/></SelectTrigger><SelectContent><SelectItem value="ESPN">ESPN</SelectItem><SelectItem value="Yahoo">Yahoo</SelectItem><SelectItem value="Sleeper">Sleeper</SelectItem><SelectItem value="Other">Other</SelectItem></SelectContent></Select>{error("platform")}</label>
      {!compact && <label className="wide"><span>What should we automate first? <em>Optional</em></span><Textarea value={data.wish} onChange={e => update("wish", e.target.value)} placeholder="Weekly waiver plans, commissioner recaps…"/></label>}
    </div>
    <Button type="submit" disabled={loading} className="form-submit">{loading ? <><RefreshCw className="spin"/> Preparing access…</> : <>Join the Founder Beta <ArrowRight/></>}</Button>
    <p className="reassurance"><ShieldCheck/> No payment required. No silent roster changes. No spam.</p>
  </form>;
}

function Dashboard({ evidence }: { evidence: () => void }) {
  return <div className="dashboard-shell">
    <div className="dash-top"><div><span className="dash-mark">LP</span><b>Command Center</b></div><p><i/> Fictional product demonstration</p><span><RefreshCw/> Synced 8m ago</span></div>
    <Tabs defaultValue="overview" className="dash-tabs">
      <TabsList className="dash-list"><TabsTrigger value="overview">Overview</TabsTrigger><TabsTrigger value="decisions">Decisions <Badge>3</Badge></TabsTrigger><TabsTrigger value="pulse">League Pulse</TabsTrigger><TabsTrigger value="schedule">Automation</TabsTrigger></TabsList>
      <TabsContent value="overview" className="dash-content"><div className="dash-grid">
        <section className="match-card"><div className="card-label"><span>WEEK 8 · PROJECTED MATCHUP</span><b>Sunday · 1 PM</b></div>
          <div className="teams"><div><span className="avatar home">FW</span><p><b>Fourth & Wrong</b><small>5–2 · You</small></p><strong>118.4</strong></div><em>VS</em><div><strong>112.8</strong><p><b>Sunday Scaries</b><small>4–3 · #5</small></p><span className="avatar">SS</span></div></div>
          <div className="share"><span>Projection share</span><b>51.2% / 48.8%</b></div><Progress value={51.2} className="projection"/>
          <p className="honesty-note"><CircleAlert/> Projection share is not a win probability.</p>
        </section>
        <section className="brief-card"><div className="brief-head"><span><Sparkles/> MORNING INTELLIGENCE BRIEF</span><Badge>3 actions</Badge></div><h3>Your biggest edge is hiding at FLEX.</h3><p>One lineup move improves your projection. Two roster risks need attention before Sunday.</p><div className="brief-stats"><div><b>+3.8</b><span>Lineup edge</span></div><div><b>4</b><span>Waiver targets</span></div><div><b>2</b><span>Trade matches</span></div><div className="risk"><b>2</b><span>Roster risks</span></div></div></section>
        <section className="decision-card"><div className="card-label"><span>DECISION QUEUE</span><b>Priority 01</b></div><div className="decision-main"><span><TrendingUp/></span><div><small>LINEUP LAB</small><h3>Move T. Spears into FLEX</h3><p>Projected improvement: <b>+3.8 pts</b></p></div><Badge>High confidence</Badge></div><div className="chips"><span><Check/> Eligible</span><span><Check/> Healthy</span><span><Check/> Projection edge</span></div><div className="decision-actions"><Button onClick={evidence} variant="outline"><FileCheck2/> Evidence</Button><Button><Check/> Approve</Button><Button variant="ghost" size="icon" aria-label="Dismiss"><X/></Button></div><p className="approval-caption">Approval records your decision. It does not change ESPN.</p></section>
        <section className="power-card"><div className="card-label"><span>POWER RANKINGS</span><b>After Week 7</b></div><ol><li><b>1</b><span>Fourth & Wrong<small>5–2 · 842 PF</small></span><em>↑2</em></li><li><b>2</b><span>Sunday Scaries<small>4–3 · 817 PF</small></span><em>—</em></li><li><b>3</b><span>Hurts So Good<small>5–2 · 799 PF</small></span><em className="down">↓2</em></li></ol></section>
      </div></TabsContent>
      <TabsContent value="decisions" className="dash-content"><div className="panel-list">{[["01","Upgrade FLEX by +3.8 projected points","Lineup Lab · High confidence"],["02","Add J. McMillan before waivers","Waiver Radar · Drop candidate found"],["03","Monitor D. Samuel injury status","Roster Risk · Update expected Friday"]].map(([n,t,s],i)=><div key={n}><b>{n}</b>{i===0?<TrendingUp/>:i===1?<Radar/>:<CircleAlert/>}<p><strong>{t}</strong><small>{s}</small></p><Button onClick={i===0?evidence:undefined} variant="outline">Review</Button></div>)}</div></TabsContent>
      <TabsContent value="pulse" className="dash-content"><div className="pulse-panel"><div><Badge>WEEK 7 STORYLINE</Badge><h3>Fourth & Wrong jumps two spots after the week’s biggest comeback.</h3><p>The closest matchup came down to Monday night while Sunday Scaries survived a 19-point bench mistake.</p><Button variant="outline"><MessageSquareText/> Preview recap</Button></div><div className="rank-bars"><span><b>#1 Fourth & Wrong</b><i style={{width:"94%"}}/></span><span><b>#2 Sunday Scaries</b><i style={{width:"83%"}}/></span><span><b>#3 Hurts So Good</b><i style={{width:"74%"}}/></span></div></div></TabsContent>
      <TabsContent value="schedule" className="dash-content"><div className="automation-panel">{[["THU","7:30 AM","Injury & matchup scan","ON"],["SUN","9:00 AM","Lineup intelligence brief","ON"],["MON","11:45 PM","Weekly recap draft","ON"],["TUE","7:15 AM","Waiver Radar report","OFF"]].map(row=><div key={row[0]}><span>{row[0]}</span><b>{row[1]}</b><p>{row[2]}</p><em className={row[3]==="ON"?"on":""}>{row[3]}</em></div>)}</div></TabsContent>
    </Tabs>
  </div>;
}

export default function Home() {
  const [betaOpen, setBetaOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [data, setData] = useState<BetaData>({name:"",email:"",role:"",leagues:"",platform:"ESPN",wish:""});
  const openBeta = (role?: string) => { if (role) setData(v=>({...v,role})); setBetaOpen(true); };
  return <main id="top">
    <header className="site-header"><div className="nav-wrap"><Logo/><nav className="desktop-nav"><a href="#product">Product</a><a href="#how">How It Works</a><a href="#features">Features</a><a href="#safety">Safety</a><a href="#founder-beta">Founder Beta</a></nav><a href="/sign-in" className="nav-signin">Sign in</a><Button onClick={()=>openBeta()} className="nav-cta">Get Early Access <ArrowRight/></Button>
      <Sheet><SheetTrigger asChild><Button variant="outline" size="icon" className="mobile-menu" aria-label="Open navigation"><Menu/></Button></SheetTrigger><SheetContent className="mobile-sheet"><SheetHeader><SheetTitle><Logo/></SheetTitle><SheetDescription>Your weekly fantasy command center.</SheetDescription></SheetHeader><nav>{[["Product","#product"],["How It Works","#how"],["Features","#features"],["Safety","#safety"],["Founder Beta","#founder-beta"]].map(([label,href],i)=><SheetClose asChild key={label}><a href={href}><span>0{i+1}</span>{label}<ChevronRight/></a></SheetClose>)}</nav><Button onClick={()=>openBeta()} className="mobile-sheet-cta">Join the Founder Beta <ArrowRight/></Button><SheetClose asChild><a href="/sign-in" className="mobile-sheet-signin">Already have an account? <b>Sign in</b></a></SheetClose></SheetContent></Sheet>
    </div></header>

    <section className="hero" id="product"><div className="field-lines"/><div className="hero-copy"><p className="kicker"><span/> THE INTELLIGENT OPERATING SYSTEM FOR YOUR FANTASY LEAGUE</p><h1>Put your fantasy league under <em>intelligent control.</em></h1><p className="hero-lede">LEAGUEPILOT AI turns your ESPN league into a weekly command center—lineup upgrades, waiver plans, realistic trade matches, power rankings, automated alerts, and group-chat recaps, all backed by real league data and kept under your approval.</p><div className="hero-actions"><Button onClick={()=>openBeta()} className="primary-cta">Join the Founder Beta <ArrowRight/></Button><Button asChild variant="outline" className="secondary-cta"><a href="#how">▶ &nbsp; Explore the Product</a></Button></div><div className="trust-strip"><span><Check/> ESPN-first intelligence</span><span><Check/> Read-only league connection</span><span><Check/> Human approval stays on</span><span><Check/> Rules-only mode needs no paid AI</span></div></div><div className="dashboard-wrap"><Dashboard evidence={()=>setEvidenceOpen(true)}/></div></section>

    <section className="section problem" id="how"><div className="section-heading centered"><p className="kicker">THE REAL WEEKLY PROBLEM</p><h2>Fantasy leagues don’t have an information problem. <em>They have a decision problem.</em></h2><p>The useful signal is scattered across projections, injuries, free agents, rosters, deadlines, and group chats. LEAGUEPILOT AI organizes the week around what needs your attention.</p></div><div className="comparison">
      <article className="old-way"><div className="compare-title"><span><X/></span><p><small>THE OLD WAY</small><b>Six tabs. One tired manager.</b></p></div><div className="chaos">{[[BarChart3,"Projections"],[CircleAlert,"Injuries"],[SearchCheck,"Waivers"],[RefreshCw,"Trades"],[Clock3,"Deadlines"],[MessageSquareText,"Recaps"]].map(([Icon,label])=>{const C=Icon as typeof BarChart3;return <div key={String(label)}><C/><span>{String(label)}</span></div>})}</div><p>Scattered research, generic rankings, forgotten deadlines, and a quiet group chat. Then repeat it next week.</p></article>
      <span className="vs">VS</span>
      <article className="new-way"><div className="compare-title"><span><Check/></span><p><small>THE LEAGUEPILOT WAY</small><b>One synchronized league snapshot.</b></p></div><div className="command-flow"><div><Gauge/><b>LEAGUE<br/>SNAPSHOT</b></div><ul><li><ListChecks/> Prioritized decisions</li><li><CalendarClock/> Scheduled analysis</li><li><FileCheck2/> Transparent evidence</li><li><Send/> Shareable content</li></ul></div><p>One operating system for personal intelligence, league-wide analysis, automation, and entertainment.</p></article>
    </div></section>

    <section className="section features" id="features"><div className="section-heading split"><div><p className="kicker">ONE LEAGUE. ONE SOURCE OF TRUTH.</p><h2>Every tool works from the <em>same real snapshot.</em></h2></div><p>Most fantasy products solve one isolated task. LEAGUEPILOT AI connects the entire weekly cycle so each recommendation understands your roster, your league, and your deadline.</p></div><div className="feature-grid">{features.map(({icon:Icon,title,eyebrow,copy,tone},i)=><article className={`feature-card ${tone} f${i+1}`} key={title}><div className="feature-icon"><Icon/></div><p className="feature-eyebrow">{eyebrow}</p><h3>{title}</h3><p>{copy}</p><div className="feature-demo">{i===0?<><span>BENCH · D. Swift</span><ArrowRight/><b>START · T. Spears <em>+3.8</em></b></>:i===1?<><b>J. McMillan · WR</b><i className="mini-bar"/><small>Drop candidate found · FAAB 7–11%</small></>:i===2?<><span>You send<br/><b>WR depth</b></span><RefreshCw/><span>You receive<br/><b>RB stability</b></span></>:i===3?<ol><li>#1 Fourth & Wrong <em>↑2</em></li><li>#2 Sunday Scaries</li><li>#3 Hurts So Good <em className="down">↓2</em></li></ol>:i===4?<><span><b>THU</b> Risk scan</span><span className="active"><b>SUN</b> Lineup brief</span><span><b>TUE</b> Waivers</span></>:<><span><Check/> Snapshot · 8m ago</span><span><Check/> Injury status verified</span><span><CircleAlert/> Weather unknown</span></>}</div></article>)}</div></section>

    <section className="section workflow"><div className="section-heading centered dark"><p className="kicker">FROM LEAGUE DATA TO CLEAR ACTION</p><h2>Your weekly intelligence cycle, <em>organized.</em></h2><p>Five steps turn scattered league information into decisions you understand and content your league wants to read.</p></div><Tabs defaultValue="connect" className="workflow-tabs"><TabsList className="workflow-list">{workflow.map(x=><TabsTrigger key={x.id} value={x.id}><span>{x.n}</span>{x.label}</TabsTrigger>)}</TabsList>{workflow.map(({id,n,label,title,copy,icon:Icon})=><TabsContent value={id} key={id} className="workflow-content"><div className="workflow-visual"><span>{n}</span><Icon/><i/><i/><i/></div><div><p className="kicker">STEP {n} · {label.toUpperCase()}</p><h3>{title}</h3><p>{copy}</p><aside><LockKeyhole/><span><b>Built for responsible access.</b> Sensitive ESPN credentials and notification targets are encrypted before storage.</span></aside></div></TabsContent>)}</Tabs></section>

    <section className="section approval" id="safety"><div className="approval-copy"><p className="kicker">HUMAN APPROVAL, ALWAYS</p><h2>Intelligent automation without <em>handing over your team.</em></h2><p>LEAGUEPILOT AI automates research, scheduled analysis, reporting, and notifications. It does not silently submit lineup changes, waiver claims, or trades.</p><blockquote><Bot/><span>AI can recommend.<br/><b>Only you can approve.</b></span></blockquote><ul>{["See estimated impact before acting","Inspect confidence, evidence, and risks","Approve or dismiss every recommendation","Keep a clear accountability trail"].map(x=><li key={x}><Check/>{x}</li>)}</ul></div>
      <div className="approval-demo"><div className="approval-top"><Badge>LINEUP LAB</Badge><span>Priority 01 of 03</span></div><h3>Move T. Spears into your FLEX.</h3><p>Replace D. Swift before Sunday’s early window.</p><div className="impact"><div><small>EST. IMPACT</small><b>+3.8 pts</b></div><div><small>CONFIDENCE</small><b className="green">HIGH</b></div><div><small>RISK FLAGS</small><b>1</b></div></div><div className="evidence-preview"><b><FileCheck2/> Evidence</b><p><Check/> Eligible at FLEX under league settings</p><p><Check/> Higher current verified projection</p><p><CircleAlert/> Monitor late-week practice status</p></div><Button onClick={()=>setEvidenceOpen(true)} variant="outline" className="full-button"><SearchCheck/> Open evidence drawer</Button><div className="approve-row"><Button variant="outline"><X/> Dismiss</Button><Button><Check/> Approve decision</Button></div><p className="approval-caption"><ShieldCheck/> Approval creates a record. It does not execute the move in ESPN.</p></div>
    </section>

    <section className="section honesty"><div className="section-heading centered"><p className="kicker">RADICAL DATA HONESTY</p><h2>No made-up certainty. <em>No mystery numbers.</em></h2><p>A useful recommendation should show what LEAGUEPILOT AI knows, what it does not know, and why the recommendation exists.</p></div><div className="honesty-compare"><article className="vague"><Badge variant="destructive"><X/> VAGUE TOOL</Badge><h3>“Start Spears. He’s a smash play.”</h3><div className="mystery">87<small>AI SCORE</small></div><p>Source unknown · Confidence unexplained · Missing data hidden</p></article><ArrowRight className="honesty-arrow"/><article className="receipt"><Badge><Check/> LEAGUEPILOT</Badge><h3>Start T. Spears at FLEX</h3><div className="receipt-stats"><span><small>EST. IMPACT</small><b>+3.8 pts</b></span><span><small>FRESHNESS</small><b>8 min</b></span><span><small>CONFIDENCE</small><b>High</b></span></div><div className="chips"><span><Check/> Position eligible</span><span><Check/> Source available</span><span><CircleAlert/> One risk</span></div></article></div><div className="principles">{[[CircleAlert,"Missing stays missing","No fake zeroes or hidden gaps."],[LineChart,"Share ≠ probability","Projection share is labeled honestly."],[Bot,"AI gets bounded facts","Model output cannot authorize actions."],[ShieldCheck,"Rules remain available","Provider failure has a deterministic fallback."]].map(([Icon,t,c])=>{const C=Icon as typeof CircleAlert;return <div key={String(t)}><C/><p><b>{String(t)}</b><span>{String(c)}</span></p></div>})}</div></section>

    <section className="section chat"><div className="chat-copy"><p className="kicker">FOR THE WHOLE LEAGUE</p><h2>Turn weekly results into <em>league entertainment.</em></h2><p>Give the entire league another reason to stay active—with commissioner-ready recaps, power rankings, storylines, and observations.</p><ul>{["Weekly league recap","Closest matchup & biggest mover","Waiver and trade-market stories","Configured Discord or GroupMe delivery"].map(x=><li key={x}><Check/>{x}</li>)}</ul><Button onClick={()=>openBeta("Commissioner")} className="primary-cta">Join as a Commissioner <ArrowRight/></Button></div><div className="chat-window"><div className="chat-head"><span>LP</span><p><b># weekly-recap</b><small>Sunday League · Discord preview</small></p><em>Configured channel</em></div><div className="message"><span><WandSparkles/></span><div><p className="bot-name">LEAGUEPILOT AI <Badge>BOT</Badge><small>Today at 8:02 AM</small></p><article><p className="kicker">WEEK 7 · MONDAY MORNING HUDDLE</p><h3>Fourth & Wrong steals the spotlight.</h3><p>A 21-point Monday comeback created the week’s closest finish and sent the new leader two spots up the rankings.</p><div><span>🏆 <b>Biggest mover</b><br/>Fourth & Wrong · ↑2</span><span>⚡ <b>Closest matchup</b><br/>1.6-point margin</span><span>📈 <b>Waiver story</b><br/>McMillan breaks out</span></div><blockquote>“The Sunday Scaries survived the bench decision. The group chat may not.”</blockquote></article><p className="reactions">🔥 6 &nbsp; 😂 4 &nbsp; 🏆 3</p></div></div><p className="chat-note"><LockKeyhole/> Fictional demo. Delivery only occurs through a channel you configure.</p></div></section>

    <section className="section audiences"><div className="section-heading centered"><p className="kicker">BUILT FOR EVERY KIND OF LEAGUE PLAYER</p><h2>Choose your <em>competitive advantage.</em></h2></div><div className="audience-grid">{[[Target,"Competitive managers","See every lineup, waiver, and trade opportunity before your opponents do.","Manager","Get My Weekly Edge"],[Zap,"Busy managers","Receive the few decisions that matter before the week’s biggest deadlines.","Manager","Stay Ahead on Less Time"],[Users,"Commissioners","Create recaps, rankings, storylines, and group-chat activity without writing it all.","Commissioner","Upgrade My League"]].map(([Icon,t,c,r,cta],i)=>{const C=Icon as typeof Target;return <article key={String(t)}><span>0{i+1}</span><C/><h3>{String(t)}</h3><p>{String(c)}</p><Button onClick={()=>openBeta(String(r))} variant="ghost">{String(cta)} <ArrowRight/></Button></article>})}</div></section>

    <section className="section tiers"><div className="section-heading split"><div><p className="kicker">PLANNED PRODUCT DIRECTIONS</p><h2>Start with the help <em>your league needs.</em></h2></div><p>These early-access directions are intentionally transparent. Final pricing and packaging will be shaped by the Founder Beta.</p></div><div className="tier-grid">{[["Free","The essentials for one team.",["One league","Lineup alerts","Basic power rankings","Rules-based reports"]],["Pro","The manager command center.",["Waiver plans","Trade Finder","Advanced explanations","Scheduled chat delivery"]],["Commissioner","A more active league.",["League history","Branded recaps","Awards and storylines","Engagement features"]]].map(([name,desc,items],i)=><article key={String(name)} className={i===1?"featured":""}>{i===1&&<Badge>FOUNDER FAVORITE</Badge>}<p>{String(name)}</p><h3>{String(desc)}</h3><ul>{(items as string[]).map(x=><li key={x}><Check/>{x}</li>)}</ul><Button onClick={()=>openBeta(i===2?"Commissioner":"Manager")} variant={i===1?"default":"outline"}>Join the Founder Beta <ArrowRight/></Button></article>)}</div><p className="tier-note"><CircleAlert/> Intended product directions—not live billing plans. Final pricing will be shaped by the Founder Beta.</p></section>

    <section className="section faq"><div className="faq-intro"><p className="kicker">STRAIGHT ANSWERS</p><h2>Before you hand us <em>your league.</em></h2><p>Here’s exactly what LEAGUEPILOT AI does—and what it deliberately does not do.</p><Button onClick={()=>openBeta()} variant="outline">Still interested? Join the beta <ArrowRight/></Button></div><Accordion type="single" collapsible className="faq-list">{faqs.map(([q,a],i)=><AccordionItem value={`f${i}`} key={q}><AccordionTrigger><span><em>0{i+1}</em>{q}</span></AccordionTrigger><AccordionContent>{a}</AccordionContent></AccordionItem>)}</Accordion></section>

    <section className="final-cta" id="founder-beta"><div className="final-lines"/><div className="final-copy"><p className="kicker">HELP BUILD THE NEXT ERA OF FANTASY MANAGEMENT</p><h2>Your league already has the data. <em>Put it to work.</em></h2><p>Join the Founder Beta and help shape the command center built for smarter decisions, easier weekly management, and better league conversations.</p><div className="founder-points"><span><b>01</b> Shape the workflow</span><span><b>02</b> Influence packaging</span><span><b>03</b> Get early access</span></div></div><div className="final-form"><div className="form-head"><div><p className="kicker">FOUNDER BETA</p><h3>Request early access.</h3></div><ShieldCheck/></div><BetaForm data={data} setData={setData}/></div></section>

    <footer className="site-footer"><div className="footer-main"><div><Logo light/><p>The intelligent weekly operating system for ESPN fantasy football leagues.</p></div><div className="footer-links"><div><b>Product</b><a href="#product">Command Center</a><a href="#features">Features</a><a href="#how">How It Works</a></div><div><b>Trust</b><a href="#safety">Human Approval</a><span>Privacy <em>Coming soon</em></span><span>Terms <em>Coming soon</em></span></div><div><b>Company</b><a href="#founder-beta">Founder Beta</a><span>Contact <em>Coming soon</em></span></div></div></div><div className="footer-bottom"><p>© 2026 Colton Wood / QuntmTech. All rights reserved.</p><p>Not affiliated with, endorsed by, or sponsored by ESPN or The Walt Disney Company.</p></div></footer>

    <div className="mobile-sticky"><Button onClick={()=>openBeta()}>Join the Founder Beta <ArrowRight/></Button></div><Button variant="outline" size="icon" className="back-top" onClick={()=>window.scrollTo({top:0,behavior:"smooth"})} aria-label="Back to top">↑</Button>
    <Dialog open={betaOpen} onOpenChange={setBetaOpen}><DialogContent className="beta-dialog"><DialogHeader><p className="kicker">FOUNDING ACCESS</p><DialogTitle>Help shape fantasy’s intelligent command center.</DialogTitle><DialogDescription>Your entries remain if you close this window. No payment and no silent roster access.</DialogDescription></DialogHeader><BetaForm data={data} setData={setData} compact/></DialogContent></Dialog>
    <Sheet open={evidenceOpen} onOpenChange={setEvidenceOpen}><SheetContent className="evidence-sheet"><SheetHeader><Badge>DECISION EVIDENCE</Badge><SheetTitle>Why LEAGUEPILOT recommends this move</SheetTitle><SheetDescription>Fictional demo · Snapshot synced 8 minutes ago</SheetDescription></SheetHeader><div className="evidence-body"><div className="evidence-impact"><small>ESTIMATED PROJECTION CHANGE</small><b>+3.8 points</b><Progress value={78}/><span>High recommendation confidence</span></div><section><h4>Verified evidence</h4><p><Check/> T. Spears is FLEX-eligible in the current settings.</p><p><Check/> His current projection is 3.8 points higher.</p><p><Check/> Both players are in the latest snapshot.</p></section><section className="risk-box"><h4>Risk flags</h4><p><CircleAlert/> Monitor late-week practice participation.</p></section><section><h4>Data provenance</h4><div><span>Roster & eligibility</span><b>ESPN snapshot</b></div><div><span>Player status</span><b>Verified injury feed</b></div><div><span>Snapshot freshness</span><b>8 minutes</b></div></section><p className="evidence-fine">Fictional data. Approval records a decision but does not submit a lineup change to ESPN.</p></div><div className="evidence-footer"><SheetClose asChild><Button variant="outline">Keep reviewing</Button></SheetClose><Button><Check/> Approve decision</Button></div></SheetContent></Sheet>
  </main>;
}
