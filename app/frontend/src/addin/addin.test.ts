import { beforeAll, describe, expect, it, vi } from "vitest";

// Minimal Office.js stand-in: enough for the helpers, without loading the CDN script.
const setSelectedDataAsync = vi.fn();
beforeAll(() => {
  vi.stubGlobal("Office", {
    onReady: vi.fn(),
    CoercionType: { Text: "text" },
    AsyncResultStatus: { Succeeded: "succeeded", Failed: "failed" },
    context: {
      requirements: { isSetSupported: (_: string, v: string) => v === "1.10" },
      mailbox: { item: { body: { setSelectedDataAsync } } },
    },
  });
});

describe("add-in helpers", () => {
  it("inserts at the cursor as plain text (never replaces the body)", async () => {
    const { insertAtCursor, HELLO_TEXT } = await import("./office");
    setSelectedDataAsync.mockImplementation((_t: string, _o: unknown, cb: (r: unknown) => void) => cb({ status: "succeeded" }));
    await insertAtCursor(HELLO_TEXT);
    expect(setSelectedDataAsync).toHaveBeenCalledWith(HELLO_TEXT, { coercionType: "text" }, expect.any(Function));
  });

  it("reads compose metadata as counts and types only", async () => {
    const { readItemContext } = await import("./office");
    const ok = (value: unknown) => (cb: (r: unknown) => void) => cb({ status: "succeeded", value });
    const compose = {
      subject: { getAsync: vi.fn() },
      to: { getAsync: ok([{ emailAddress: "a@x.com" }, { emailAddress: "b@x.com" }]) },
      cc: { getAsync: ok([{ emailAddress: "c@x.com" }]) },
      getComposeTypeAsync: ok({ composeType: "reply" }),
      conversationId: "conv-1",
    };
    const ctx = await readItemContext(compose as unknown as Office.MessageCompose);
    expect(ctx).toEqual({ mode: "compose", composeType: "reply", recipients: 3, hasConversationId: true });
    expect(JSON.stringify(ctx)).not.toContain("@");
  });

  it("reads read-mode metadata synchronously", async () => {
    const { readItemContext } = await import("./office");
    const read = { subject: "Hello", to: [{}, {}], cc: [], conversationId: "" };
    const ctx = await readItemContext(read as unknown as Office.MessageRead);
    expect(ctx).toEqual({ mode: "read", composeType: null, recipients: 2, hasConversationId: false });
  });
});
