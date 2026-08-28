# LEAGUEPILOT AI landing-page build brief

Paste this brief into Claude Design or ChatGPT Sites to create the product marketing site.

## Assignment

Design and build a complete, polished, interactive, mobile-first homepage for **LEAGUEPILOT AI**.
Deliver a functional, clickable preview rather than a static mockup or generic SaaS template. Build
the experience from navigation through the final conversion form and footer. It should feel like a
premium fantasy-sports command center and explain the value within five seconds.

The primary conversion is **Join the Founder Beta**. The secondary conversion is **Explore the
Product**. Do not pretend that public billing or unrestricted SaaS onboarding already exists.

## Product truth

LEAGUEPILOT AI is an ESPN-first fantasy-football intelligence and league-automation platform. It
turns a synchronized league snapshot into:

- injury-aware lineup recommendations;
- waiver targets compared with realistic drop candidates;
- trade ideas scored for fairness and mutual roster fit;
- matchup projections and transparent power rankings;
- weekly league recaps and commissioner-ready group-chat content;
- scheduled analysis with optional Discord or GroupMe delivery;
- an evidence-rich decision queue with approve and dismiss history.

It automates research, prioritization, reporting and alerts. It does **not** silently submit ESPN
lineup, waiver or trade actions. Rules-only narration costs no model tokens; optional model providers
are used only for prose and fall back to deterministic narration when unavailable.

The central positioning is:

> LEAGUEPILOT AI combines personal team intelligence, league-wide analysis, weekly automation and
> group-chat entertainment inside one approval-controlled command center.

The emotional promise is less time digging through scattered information and more confidence making
moves, winning matchups and keeping the league active.

## Audience

Design for competitive managers, busy casual managers and commissioners. Use normal fantasy-football
language, not engineering jargon. Competitive managers want an edge; busy managers want prioritized
deadlines; commissioners want an active, entertaining league.

## Recommended hero

**Eyebrow:** THE INTELLIGENT OPERATING SYSTEM FOR YOUR FANTASY LEAGUE

**Headline:** Put your fantasy league under intelligent control.

**Supporting copy:** LEAGUEPILOT AI turns your ESPN league into a weekly command center—lineup
upgrades, waiver plans, realistic trade matches, power rankings, automated alerts and group-chat
recaps, all backed by real league data and kept under your approval.

**Primary CTA:** Join the Founder Beta

**Secondary CTA:** Explore the Product

Trust points: ESPN-first intelligence · Read-only connection · Human approval stays on · Rules mode
requires no paid AI model.

## Visual system

The design should combine a professional sports control room, premium editorial sports media and a
polished financial dashboard. Avoid generic purple AI gradients, cartoon footballs, sportsbook
imagery, fake stock athletes, excessive glassmorphism and repetitive card grids.

Use the existing application palette:

- deep forest `#122F28`;
- primary green `#1D5949`;
- secondary green `#2F7A63`;
- warm paper `#F5F1E8`;
- secondary paper `#ECE6DA`;
- panel white `#FFFDF8`;
- lime `#B8DC73`;
- gold `#E4B949`;
- dark text `#17221F`;
- muted text `#6E7772`;
- risk red `#B75042`;
- information blue `#4B7199`.

Use Inter, Geist or a comparable clean sans-serif. Add restrained field lines, playbook routes,
schedule markers and statistical patterns. A strong `LP AI` monogram, route diagram, compass or
command-center mark is appropriate; do not use a generic robot head.

## Page structure

1. Sticky navigation: Product, How It Works, Features, Safety, Founder Beta and Get Early Access.
2. Hero with the copy above and a large interactive product demonstration.
3. Problem section: “Fantasy leagues don’t have an information problem. They have a decision
   problem.” Contrast six scattered tabs with one synchronized operating system.
4. Feature bento: Lineup Lab, Waiver Radar, Trade Finder, League Pulse, Automation Control, Evidence
   and Data Quality. Give every feature a small visual demonstration and benefit-led copy.
5. Interactive workflow: Connect → Synchronize → Analyze → Approve → Share. Clicking each step must
   change the accompanying visual.
6. Approval section built around “AI can recommend. Only you can approve.” Show recommendation,
   impact, confidence, evidence, risk flags and decision controls.
7. Data-honesty section: missing projections remain missing; projection share is not win probability;
   demos are fictional; model output cannot authorize actions; fallback is deterministic.
8. Commissioner/group-chat section with a clearly fictional Discord or GroupMe recap.
9. Audience paths for competitive managers, busy managers and commissioners. Each path opens the
   beta form with the relevant role selected.
10. Planned tiers—Free, Pro and Commissioner—without invented prices or checkout buttons. Mark
    packaging as subject to the Founder Beta.
11. Accessible FAQ.
12. Dark final conversion section: “Your league already has the data. Put it to work.”
13. Footer with product links, placeholders for real legal/contact URLs, ownership and the ESPN
    non-affiliation disclaimer.

## Hero demonstration

Create a convincing interactive dashboard showing a fictional weekly matchup, **projection share**,
lineup edge, waiver and trade counts, roster risk, a morning brief, decision queue, power rankings and
weekly schedule. Label it **Fictional product demonstration**. Animate recommendation arrival,
evidence chips, the weekly schedule and a recap moving into group chat. Never make demo data appear to
belong to a real customer.

## Founder Beta form

Collect first name, email, role (Manager, Commissioner or Both), number of leagues, primary platform
and an optional “What should LeaguePilot automate first?” field. Provide validation, loading, error,
success and post-submit states. If no backend exists, isolate the submission adapter and keep the
preview honest; do not leave a dead button.

## Conversion requirements

- Keep one dominant CTA and repeat it after major persuasion sections.
- Use benefit-driven headings and short, scannable copy.
- Demonstrate the product instead of relying on abstract claims.
- Address action safety, private leagues, AI cost and provider support before the final form.
- Preserve form entries if a modal closes accidentally.
- Use a compact mobile CTA without covering content.
- Do not use fake scarcity, countdowns, testimonials, customer counts, logos, ratings or metrics.
- Leave dormant components for real pilot evidence to be enabled later.

## Required interactions

Implement smooth navigation, a mobile drawer, product tabs, interactive hero, weekly workflow,
evidence disclosure, FAQ accordion, beta form, loading/success states, visible focus states and
reduced-motion support. Every control that looks functional must work.

Design mobile first at about 375 pixels. Verify no horizontal scrolling, large tap targets, forms that
work with the mobile keyboard, stacked dashboard modules, contained tables and smooth animation.
Expand cleanly through 1440–1600 pixel desktop widths.

## Accuracy restrictions

- Never guarantee wins or accuracy.
- Never fabricate projections, results, customers or testimonials.
- Never call projection share a win probability.
- Never claim the product submits ESPN roster changes.
- Never imply official ESPN affiliation.
- Never advertise Yahoo or Sleeper support as live.
- Never invent prices.
- Label every example as fictional.
- Distinguish shipped features from planned features.
- Never expose cookies, webhook targets, API keys or technical secrets.

## FAQ truth

- Roster changes are approval-only and are not submitted to ESPN.
- Private ESPN league credentials are encrypted before storage and never returned by the API.
- A paid AI model is optional.
- Model or provider failure uses deterministic narration.
- ESPN is the initial supported platform; Yahoo and Sleeper are future possibilities.
- This is season-long fantasy intelligence, not betting or DFS software.
- LEAGUEPILOT AI is not affiliated with or endorsed by ESPN or The Walt Disney Company.
- Founder Beta pricing is not finalized.

## Final quality gate

After the first implementation, review the page as a first-time manager. Confirm five-second product
clarity, strengthen generic headlines, remove repetition, test every CTA, inspect multiple mobile
widths, fix overflow/contrast/spacing, verify accessibility and confirm that no planned capability is
presented as shipped. Complete a final conversion-focused polish pass before delivery.
