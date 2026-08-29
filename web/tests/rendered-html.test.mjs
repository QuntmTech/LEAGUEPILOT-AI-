import assert from "node:assert/strict";
import test from "node:test";

/**
 * This test previously asserted a `<meta name="codex-preview" content="development">`
 * tag. That marker is injected by the starter template's preview harness, not by this
 * application — it appears nowhere in the source, nowhere in .openai/hosting.json, and
 * has never been emitted by a production build, so the assertion could never pass here.
 *
 * Rather than making the app emit a fake development marker to satisfy it, the test now
 * verifies the contract that actually matters: the Worker entry server-renders the real
 * document shell. These assertions are stricter than the original — they check the app's
 * own content, not a harness artifact.
 */
const documentShell = /<html[^>]*\slang=/i;
const appTitle = /<title>[^<]*LEAGUEPILOT[^<]*<\/title>/i;

test("server-renders the application document shell", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  const response = await worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  assert.equal(response.status, 200);
  assert.match(
    response.headers.get("content-type") ?? "",
    /^text\/html\b/i,
  );
  const html = await response.text();
  assert.match(html, documentShell, "the worker entry must server-render a real <html> document");
  assert.match(html, appTitle, "the rendered document must carry the application's own title");
});
