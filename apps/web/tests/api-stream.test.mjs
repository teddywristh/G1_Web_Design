// Run with: node --test apps/web/tests
// api.js reads the DOM and fetch at import time, so stub them before importing it.
import assert from "node:assert/strict";
import { test } from "node:test";

const status = { hidden: true, textContent: "" };
globalThis.document = {
  querySelector: (selector) => (selector === "#system-status" ? status : null),
};
let respond;
globalThis.fetch = async (url, options) => respond(url, options);
const { api, setCsrf } = await import("../js/api.js");

const encoder = new TextEncoder();

// A streaming Response whose body arrives in the given byte pieces.
function sse(pieces, init = { status: 200 }) {
  const body = new ReadableStream({
    start(controller) {
      for (const piece of pieces) controller.enqueue(piece);
      controller.close();
    },
  });
  return new Response(body, { ...init, headers: { "Content-Type": "text/event-stream" } });
}

function event(payload) {
  return `event: ${payload.type}\ndata: ${JSON.stringify(payload)}\n\n`;
}

// Cut text into pieces of `size` bytes, even in the middle of a multi-byte character.
function bytesIn(text, size) {
  const bytes = encoder.encode(text);
  const pieces = [];
  for (let start = 0; start < bytes.length; start += size) pieces.push(bytes.slice(start, start + size));
  return pieces;
}

const DONE = { type: "done", response: { answer: "Thử việc tối đa 60 ngày [1]", status: "answered" } };

test("events arrive in order whatever the chunking, including split UTF-8 characters", async () => {
  const wire =
    event({ type: "stage", stage: "retrieving" }) +
    event({ type: "sources", items: [{ title: "Bộ luật Hình sự", article: "173" }] }) +
    event({ type: "claim", text: "Trộm cắp tài sản bị phạt tù [1]", citations: [] }) +
    event(DONE);
  for (const size of [1, 2, 3, 5, 64, 10_000]) {
    respond = () => sse(bytesIn(wire, size));
    const seen = [];
    const final = await api.stream("/rag/ask/stream", { question: "q" }, (e) => seen.push(e.type));
    assert.deepEqual(seen, ["stage", "sources", "claim", "done"], `chunk size ${size}`);
    assert.equal(final.answer, DONE.response.answer);
  }
});

test("CRLF line ends and keep-alive comments are handled", async () => {
  const wire = ": keep-alive\r\n\r\n" + event(DONE).replace(/\n/g, "\r\n");
  respond = () => sse(bytesIn(wire, 7));
  const seen = [];
  const final = await api.stream("/rag/ask/stream", {}, (e) => seen.push(e.type));
  assert.deepEqual(seen, ["done"]);
  assert.equal(final.status, "answered");
});

test("an error event becomes an ApiError with the Vietnamese text and status", async () => {
  respond = () =>
    sse(
      bytesIn(
        event({ type: "stage", stage: "drafting" }) +
          event({ type: "error", code: "ai_authentication_failed", message: "rejected", status: 502 }),
        11,
      ),
    );
  await assert.rejects(
    () => api.stream("/rag/ask/stream", {}),
    (error) =>
      error.code === "ai_authentication_failed" &&
      error.status === 502 &&
      error.message === "Nhà cung cấp AI từ chối khóa đã chọn.",
  );
});

test("a stream that ends without a final response is reported as a lost connection", async () => {
  respond = () => sse(bytesIn(event({ type: "stage", stage: "retrieving" }), 9));
  await assert.rejects(
    () => api.stream("/rag/ask/stream", {}),
    (error) => error.code === "network" && /ngắt/.test(error.message),
  );
});

test("an HTTP error before the stream starts is a normal ApiError", async () => {
  respond = () =>
    new Response(JSON.stringify({ error: { code: "chatgpt_disconnected", message: "x" } }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    });
  await assert.rejects(
    () => api.stream("/rag/ask/stream", {}),
    (error) => error.code === "chatgpt_disconnected" && error.status === 409,
  );
});

test("the request carries the cookie, CSRF token and JSON body", async () => {
  setCsrf("csrf-123");
  let seen;
  respond = (url, options) => {
    seen = { url, options };
    return sse(bytesIn(event(DONE), 50));
  };
  await api.stream("/rag/ask/stream", { question: "Xin chào" });
  assert.match(seen.url, /\/api\/v1\/rag\/ask\/stream$/);
  assert.equal(seen.options.method, "POST");
  assert.equal(seen.options.credentials, "include");
  assert.equal(seen.options.headers["X-CSRF-Token"], "csrf-123");
  assert.deepEqual(JSON.parse(seen.options.body), { question: "Xin chào" });
});

test("the busy indicator is cleared once the stream finishes, even after a failure", async () => {
  respond = () => sse(bytesIn(event(DONE), 50));
  await api.stream("/rag/ask/stream", {});
  assert.equal(status.hidden, true);
  respond = () => sse(bytesIn(event({ type: "error", code: "x", status: 503 }), 50));
  await assert.rejects(() => api.stream("/rag/ask/stream", {}));
  assert.equal(status.hidden, true);
});
