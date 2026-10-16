import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { Api, ApiError, type Draft } from "../api/client";
import { TeamsDraft, type TeamsHost } from "./TeamsDraft";

function wrap(ui: ReactElement) {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>);
}

const DRAFT = {
  id: "d1", text: "ok, will share by 5", generator: "offline", label: "Offline stand-in", modelId: "m", tier: "default",
  routeReason: "default",
  audience: { relationship: "report", label: "your direct report", to: [], cc: [], internal: 1, external: 0 },
  styleSlice: null, learned: true, basedOn: 4, exemplars: 0, checks: [], insertAllowed: true, oneOff: false,
  timing: { totalMs: 10, modelMs: null }, channel: "chat", chatUsers: ["rahul.verma@kestrel.example"],
} as Draft; // prettier-ignore

function host() {
  return {
    openChat: vi.fn<TeamsHost["openChat"]>().mockResolvedValue(undefined),
    close: vi.fn<TeamsHost["close"]>(),
  };
}

describe("Teams dialog", () => {
  it("drafts a reply to the message it was opened on and copies it", async () => {
    const api = new Api("", async () => "t");
    const create = vi.spyOn(api, "createDraft").mockResolvedValue(DRAFT);
    vi.spyOn(api, "draftFeedback").mockResolvedValue(undefined);
    const user = userEvent.setup(); // installs its own clipboard: spy on it after
    const clip = vi.spyOn(navigator.clipboard, "writeText");
    const h = host();
    wrap(<TeamsDraft api={api} target={{ mode: "reply", chatId: "19:abc@thread.v2", messageId: "m1" }} prefill={false} host={h} />);
    await user.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ mode: "reply", channel: "chat", surface: "teams", conversationId: "19:abc@thread.v2", messageId: "m1" }),
      ),
    );
    await user.click(await screen.findByRole("button", { name: "Copy" }));
    await waitFor(() => expect(clip).toHaveBeenCalledWith("ok, will share by 5"));
    // Prefill is off for this organisation: Copy only.
    expect(screen.queryByRole("button", { name: "Open the chat with this text" })).toBeNull();
  });

  it("opens the chat with the text when the organisation allows it", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "createDraft").mockResolvedValue(DRAFT);
    vi.spyOn(api, "draftFeedback").mockResolvedValue(undefined);
    const user = userEvent.setup();
    const h = host();
    wrap(<TeamsDraft api={api} target={{ mode: "reply", chatId: "c", messageId: null }} prefill host={h} />);
    await user.click(screen.getByRole("button", { name: "Draft" }));
    await user.click(await screen.findByRole("button", { name: "Open the chat with this text" }));
    await waitFor(() => expect(h.openChat).toHaveBeenCalledWith(["rahul.verma@kestrel.example"], "ok, will share by 5"));
  });

  it("explains channels and excluded chats", async () => {
    const api = new Api("", async () => "t");
    const h = host();
    const { unmount } = wrap(<TeamsDraft api={api} target={{ mode: "channel", chatId: null, messageId: null }} prefill={false} host={h} />);
    expect(screen.getByText("Vanimo works in chats")).toBeInTheDocument();
    unmount();
    vi.spyOn(api, "createDraft").mockRejectedValue(
      new ApiError(409, "conversation_excluded", { by: "you", oneOffAllowed: true }),
    );
    const user = userEvent.setup();
    wrap(<TeamsDraft api={api} target={{ mode: "reply", chatId: "c", messageId: null }} prefill={false} host={h} />);
    await user.click(screen.getByRole("button", { name: "Draft" }));
    expect(await screen.findByText(/You excluded this conversation/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Draft once without saving" })).toBeInTheDocument();
  });
});
