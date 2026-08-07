import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
import {describe, expect, it, vi} from "vitest";

type WorkerRequest = {method: string; mode: string; url: string};
type FetchEvent = {
  request: WorkerRequest;
  respondWith(response: Promise<Response> | Response): void;
};
type FetchListener = (event: FetchEvent) => void;

function loadFetchListener(options: {cached?: Response; network?: () => Promise<Response>} = {}) {
  const listeners = new Map<string, FetchListener>();
  const match = vi.fn(async () => options.cached);
  const source = readFileSync(new URL("../../public/sw.js", import.meta.url), "utf8");
  const worker = {
    addEventListener: (name: string, listener: FetchListener) => listeners.set(name, listener),
    clients: {claim: vi.fn()},
    location: {origin: "http://localhost:3000"},
    skipWaiting: vi.fn()
  };
  runInNewContext(source, {
    Response,
    URL,
    caches: {
      delete: vi.fn(),
      keys: vi.fn(async () => []),
      match,
      open: vi.fn()
    },
    fetch: options.network ?? vi.fn(async () => new Response("online")),
    self: worker
  });
  return {listener: listeners.get("fetch")!, match};
}

function dispatch(listener: FetchListener, request: WorkerRequest) {
  let response: Promise<Response> | undefined;
  listener({request, respondWith: value => { response = Promise.resolve(value); }});
  return response;
}

describe("service worker", () => {
  it("does not intercept Next.js RSC or other non-navigation requests", () => {
    const {listener, match} = loadFetchListener();
    const response = dispatch(listener, {
      method: "GET",
      mode: "cors",
      url: "http://localhost:3000/es/app/leagues/league-id?_rsc=abc"
    });
    expect(response).toBeUndefined();
    expect(match).not.toHaveBeenCalled();
  });

  it("returns the cached offline document when a navigation loses the network", async () => {
    const cached = new Response("offline");
    const {listener, match} = loadFetchListener({
      cached,
      network: vi.fn(async () => { throw new TypeError("offline"); })
    });
    const response = dispatch(listener, {
      method: "GET",
      mode: "navigate",
      url: "http://localhost:3000/es/app/leagues/league-id"
    });
    await expect(response).resolves.toBe(cached);
    expect(match).toHaveBeenCalledWith("/offline", {ignoreSearch: true});
  });

  it("returns a valid 503 response instead of Response.error when the fallback is absent", async () => {
    const {listener} = loadFetchListener({
      network: vi.fn(async () => { throw new TypeError("offline"); })
    });
    const response = dispatch(listener, {
      method: "GET",
      mode: "navigate",
      url: "http://localhost:3000/es/app/leagues/league-id"
    });
    await expect(response).resolves.toMatchObject({status: 503, type: "default"});
  });
});
