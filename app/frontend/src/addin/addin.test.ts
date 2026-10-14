import { beforeAll, describe, expect, it, vi } from "vitest";

// Minimal Office.js stand-in: enough for the helpers, without loading the CDN script.
const setSelectedDataAsync = vi.fn();
const getAsync = vi.fn();
const displayReplyForm = vi.fn();
const displayReplyAllForm = vi.fn();
beforeAll(() => {
  vi.stubGlobal("Office", {
    onReady: vi.fn(),
    CoercionType: { Text: "text" },
    AsyncResultStatus: { Succeeded: "succeeded", Failed: "failed" },
    context: {
      requirements: { isSetSupported: (_: string, v: string) => v === "1.10" },
      mailbox: { item: { body: { setSelectedDataAsync, getAsync }, displayReplyForm, displayReplyAllForm } },
    },
  });
});

const ok = (value: unknown) => (cb: (r: unknown) => void) => cb({ status: "succeeded", value });

describe("add-in helpers", () => {
  it("inserts at the cursor as plain text (never replaces the body)", async () => {
    const { insertAtCursor } = await import("./office");
    setSelectedDataAsync.mockImplementation((_t: string, _o: unknown, cb: (r: unknown) => void) => cb({ status: "succeeded" }));
    await insertAtCursor("Hi Meera,\n\nDone.");
    expect(setSelectedDataAsync).toHaveBeenCalledWith("Hi Meera,\n\nDone.", { coercionType: "text" }, expect.any(Function));
  });

  it("reads the compose window: recipients, subject, conversation and compose type", async () => {
    const { readItemContext, draftMode } = await import("./office");
    const compose = {
      subject: { getAsync: ok("Re: Q4 plan") },
      to: { getAsync: ok([{ emailAddress: "Meera@Kestrel.example", displayName: "Meera Iyer" }]) },
      cc: { getAsync: ok([{ emailAddress: "c@x.com", displayName: "c@x.com" }]) },
      getComposeTypeAsync: ok({ composeType: "reply" }),
      conversationId: "conv-1",
    };
    const ctx = await readItemContext(compose as unknown as Office.MessageCompose);
    expect(ctx).toEqual({
      mode: "compose",
      composeType: "reply",
      conversationId: "conv-1",
      subject: "Re: Q4 plan",
      to: [{ email: "meera@kestrel.example", name: "Meera Iyer" }],
      cc: [{ email: "c@x.com", name: null }],
      from: null,
    });
    expect(draftMode(ctx)).toBe("reply");
    expect(draftMode({ ...ctx, composeType: "newMail" })).toBe("new");
    expect(draftMode({ ...ctx, composeType: "forward" })).toBe("new");
  });

  it("reads read mode synchronously, with the sender", async () => {
    const { readItemContext, draftMode } = await import("./office");
    const read = {
      subject: "Hello",
      from: { emailAddress: "a@x.com", displayName: "Ann" },
      to: [{ emailAddress: "me@x.com", displayName: "Me" }],
      cc: [],
      conversationId: "",
    };
    const ctx = await readItemContext(read as unknown as Office.MessageRead);
    expect(ctx.mode).toBe("read");
    expect(ctx.from).toEqual({ email: "a@x.com", name: "Ann" });
    expect(ctx.conversationId).toBeNull();
    expect(draftMode(ctx)).toBe("reply");
  });

  it("reads the body only as text, and opens replies with escaped HTML", async () => {
    const { bodyText, openReply, textToHtml } = await import("./office");
    getAsync.mockImplementation((_c: unknown, cb: (r: unknown) => void) => cb({ status: "succeeded", value: "Hi" }));
    expect(await bodyText()).toBe("Hi");
    expect(getAsync).toHaveBeenCalledWith("text", expect.any(Function));
    expect(textToHtml('a < b & "c"\nd')).toBe("<div>a &lt; b &amp; &quot;c&quot;<br>d</div>");
    openReply("x", false);
    openReply("y", true);
    expect(displayReplyForm).toHaveBeenCalledWith({ htmlBody: "<div>x</div>" });
    expect(displayReplyAllForm).toHaveBeenCalledWith({ htmlBody: "<div>y</div>" });
  });
});
