/**
 * Cloudflare Worker bindings for this app.
 *
 * `cloudflare:workers` types its exported `env` as `Cloudflare.Env` — not a global `Env`
 * — and @cloudflare/workers-types ships that namespace with an empty interface for apps
 * to augment. Declaring `Env` locally inside worker/index.ts therefore left db/index.ts
 * unable to see the `DB` binding through `env`.
 *
 * Augmenting `Cloudflare.Env` is the convention wrangler follows when it generates
 * worker-configuration.d.ts, and makes one binding definition visible to every file.
 * `Env` is re-exported globally so worker/index.ts keeps its existing signature.
 */
declare namespace Cloudflare {
  interface Env {
    ASSETS: Fetcher;
    DB: D1Database;
    IMAGES: {
      input(stream: ReadableStream): {
        transform(options: Record<string, unknown>): {
          output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
        };
      };
    };
  }
}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type -- alias, not a new shape
interface Env extends Cloudflare.Env {}
