from __future__ import annotations

import html


def _shell(body: str, *, title: str) -> str:
    """Minimal branded shell. Deliberately plain: UX polish is deferred, but the security
    properties here are not — every interpolated value is escaped by the caller, there is
    no inline event handler, and no third-party asset is loaded."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{html.escape(title)}</title>
<style>
:root{{--forest:#122f28;--green:#1d5949;--paper:#f5f1e8;--card:#fffdf8;--line:#d7d1c6;--ink:#17221f;--muted:#6e7772;--red:#b75042}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;
padding:24px;background:var(--paper);color:var(--ink);
font:14px/1.6 -apple-system,BlinkMacSystemFont,sans-serif}}
.card{{width:100%;max-width:420px;padding:28px;border:1px solid var(--line);
border-radius:16px;background:var(--card);
box-shadow:0 12px 38px rgba(18,47,40,.08)}}
h1{{margin:0 0 6px;font-size:22px;letter-spacing:-.03em}}
p.sub{{margin:0 0 20px;color:var(--muted);font-size:13px}}
label{{display:block;margin:0 0 5px;font-size:12px;font-weight:700}}
input{{width:100%;min-height:44px;margin-bottom:14px;padding:0 12px;
border:1px solid var(--line);
border-radius:9px;background:#fff;font:inherit}}
input:focus-visible{{outline:3px solid var(--green);outline-offset:1px}}
button{{width:100%;min-height:46px;border:0;border-radius:9px;
background:var(--green);color:#fff;
font:inherit;font-weight:700;cursor:pointer}}
button.secondary{{margin-top:9px;background:transparent;color:var(--muted);
border:1px solid var(--line)}}
.scopes{{margin:0 0 18px;padding:12px 14px;border:1px solid var(--line);
border-radius:11px;background:var(--paper)}}
.scopes li{{margin:3px 0;font-size:13px}}.scopes ul{{margin:6px 0 0;padding-left:18px}}
.err{{margin:0 0 14px;padding:10px 12px;border:1px solid var(--red);
border-radius:9px;color:var(--red);font-size:13px}}
.note{{margin:16px 0 0;color:var(--muted);font-size:11px}}
.brand{{display:flex;align-items:center;gap:8px;margin-bottom:18px;
font-weight:900;letter-spacing:-.02em}}
.brand span{{display:grid;place-items:center;width:28px;height:28px;
border-radius:8px;background:var(--forest);color:#b8dc73;font-size:11px}}
</style></head><body><main class="card">
<div class="brand"><span>LP</span>LEAGUEPILOT AI</div>
{body}
</main></body></html>"""


SCOPE_LABELS = {
    "leaguepilot:read": "Read your leagues, rosters, recommendations and reports",
    "leaguepilot:write": "Queue syncs and analyses, and record your approve/dismiss decisions",
}


def login_page(*, request_token: str, client_name: str, scopes: list[str], error: str = "") -> str:
    """Sign-in and consent in one step.

    `request_token` carries the pending authorization request server-side. The OAuth
    parameters are never round-tripped through the browser as form fields, so a tampered
    form cannot change the redirect URI, scope or PKCE challenge that were validated.
    """
    items = "".join(
        f"<li>{html.escape(SCOPE_LABELS.get(s, s))}</li>" for s in scopes
    )
    err = f'<p class="err">{html.escape(error)}</p>' if error else ""
    name = html.escape(client_name or "An application")
    return _shell(
        f"""<h1>Authorize {name}</h1>
<p class="sub">Sign in with your LEAGUEPILOT account to continue.</p>
{err}
<div class="scopes"><b>This will allow it to:</b><ul>{items}</ul></div>
<form method="post" action="/authorize" autocomplete="on">
<input type="hidden" name="request_token" value="{html.escape(request_token)}">
<label for="email">Email</label>
<input id="email" name="email" type="email" required autocomplete="username">
<label for="password">Password</label>
<input id="password" name="password" type="password" required autocomplete="current-password">
<button type="submit" name="decision" value="allow">Sign in and authorize</button>
<button type="submit" name="decision" value="deny" class="secondary">Cancel</button>
</form>
<p class="note">LEAGUEPILOT never asks for your ESPN password or cookies here, and never
changes your ESPN team.</p>""",
        title="Authorize · LEAGUEPILOT AI",
    )


def error_page(message: str) -> str:
    return _shell(
        f'<h1>Authorization failed</h1><p class="err">{html.escape(message)}</p>'
        '<p class="note">Close this window and try again from the application.</p>',
        title="Authorization failed",
    )
