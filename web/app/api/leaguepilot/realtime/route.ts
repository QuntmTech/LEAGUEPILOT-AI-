import {
  LEAGUEPILOT_BACKEND,
  backendFetch,
  sessionToken,
  unauthorized,
} from "@/lib/leaguepilot-server";

export const dynamic = "force-dynamic";

/**
 * Server-side PocketBase realtime proxy.
 *
 * PocketBase's realtime stream authenticates with a bearer token, but this app keeps
 * that token in an HttpOnly cookie the browser cannot read. Subscribing from the
 * browser would therefore require exposing the token to JavaScript, which the
 * security model forbids.
 *
 * Instead the server holds the upstream connection: it opens PocketBase's SSE stream,
 * reads the PB_CONNECT clientId, registers the owner-scoped subscriptions with the
 * bearer token, and re-streams events to the browser. The token never leaves the server.
 *
 * PocketBase applies the same collection rules to realtime as to reads, so a client
 * only ever receives records it could already fetch.
 */
const SUBSCRIPTIONS = [
  "espn_connections",
  "job_runs",
  "recommendations",
  "reports",
  "audit_events",
];

export async function GET(request: Request) {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const upstream = await fetch(`${LEAGUEPILOT_BACKEND}/api/realtime`, {
    headers: { Accept: "text/event-stream" },
    cache: "no-store",
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return Response.json({ message: "Realtime unavailable." }, { status: 502 });
  }

  const decoder = new TextDecoder();
  const encoder = new TextEncoder();
  const reader = upstream.body.getReader();
  let registered = false;
  let buffer = "";
  let heartbeat: ReturnType<typeof setInterval> | null = null;
  let closed = false;

  /**
   * Release the upstream connection exactly once. Without this an abandoned browser
   * tab would leave a PocketBase stream open per reload, and those accumulate.
   */
  const release = (reason: string) => {
    if (closed) return;
    closed = true;
    if (heartbeat) clearInterval(heartbeat);
    reader.cancel(reason).catch(() => {});
  };

  // If the browser disconnects, tear down the upstream leg too.
  request.signal.addEventListener("abort", () => release("client disconnected"));

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      // SSE comment frames keep intermediaries (Apache, CDNs) from closing an idle
      // stream, and surface a dead connection to the client promptly.
      heartbeat = setInterval(() => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(": ping\n\n"));
        } catch {
          release("heartbeat failed");
        }
      }, 25_000);
    },
    async pull(controller) {
      if (closed) {
        controller.close();
        return;
      }
      const { done, value } = await reader.read();
      if (done) {
        release("upstream ended");
        controller.close();
        return;
      }
      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;

      // The first frame carries the clientId; register subscriptions once we have it.
      if (!registered) {
        const match = buffer.match(/"clientId"\s*:\s*"([a-zA-Z0-9]+)"/);
        if (match) {
          registered = true;
          const clientId = match[1];
          // Fire and forget: a failure here surfaces as an absence of events, and the
          // client falls back to polling rather than hanging.
          backendFetch("/api/realtime", token, {
            method: "POST",
            body: JSON.stringify({ clientId, subscriptions: SUBSCRIPTIONS }),
          }).catch(() => {});
        }
        // Keep the buffer bounded if the id never arrives.
        if (buffer.length > 8192) buffer = buffer.slice(-1024);
      }

      controller.enqueue(encoder.encode(chunk));
    },
    cancel(reason) {
      release(String(reason ?? "cancelled"));
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
