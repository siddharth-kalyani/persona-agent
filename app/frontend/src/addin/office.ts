/// <reference types="office-js" />
/** Office.js helpers for the Outlook task pane (kept free of React so they're cheap to test).
 *
 * What the pane reads from the open item, and when it leaves the pane:
 *  - the conversation ID, subject and recipients: read when the pane opens, kept in memory and
 *    sent to the Vanimo API only when you press Draft or Check (the API decides from them whether
 *    the conversation is excluded before reading any message text);
 *  - the body you're writing: read only when you press "Check before sending".
 */
import type { PersonRef } from "../api/client";

export interface ItemContext {
  mode: "compose" | "read";
  composeType: string | null; // newMail | reply | forward (Mailbox 1.10+)
  conversationId: string | null;
  subject: string | null;
  to: PersonRef[];
  cc: PersonRef[];
  /** Read mode: who sent the message you're reading. */
  from: PersonRef | null;
}

function asyncValue<T>(fn: (cb: (r: Office.AsyncResult<T>) => void) => void): Promise<T | null> {
  return new Promise((resolve) => fn((r) => resolve(r.status === Office.AsyncResultStatus.Succeeded ? r.value : null)));
}

function people(list: Office.EmailAddressDetails[] | null | undefined): PersonRef[] {
  return (list ?? [])
    .filter((a) => a?.emailAddress)
    .map((a) => ({
      email: a.emailAddress.toLowerCase(),
      name: a.displayName && a.displayName !== a.emailAddress ? a.displayName : null,
    }));
}

export async function readItemContext(item: Office.MessageCompose | Office.MessageRead): Promise<ItemContext> {
  // In read mode `subject` is a string; in compose mode it is an object with getAsync/setAsync.
  if (typeof (item as { subject?: unknown }).subject === "string") {
    const read = item as Office.MessageRead;
    const from = people(read.from ? [read.from] : [])[0] ?? null;
    return {
      mode: "read",
      composeType: null,
      conversationId: read.conversationId || null,
      subject: read.subject || null,
      to: people(read.to),
      cc: people(read.cc),
      from,
    };
  }
  const compose = item as Office.MessageCompose;
  const [to, cc, subject] = await Promise.all([
    asyncValue<Office.EmailAddressDetails[]>((cb) => compose.to.getAsync(cb)),
    asyncValue<Office.EmailAddressDetails[]>((cb) => compose.cc.getAsync(cb)),
    asyncValue<string>((cb) => compose.subject.getAsync(cb)),
  ]);
  let composeType: string | null = null;
  if (Office.context.requirements.isSetSupported("Mailbox", "1.10")) {
    const ct = await asyncValue<{ composeType: string }>((cb) =>
      (compose as unknown as { getComposeTypeAsync: (c: typeof cb) => void }).getComposeTypeAsync(cb),
    );
    composeType = ct?.composeType ?? null;
  }
  return {
    mode: "compose",
    composeType,
    conversationId: compose.conversationId || null,
    subject: subject || null,
    to: people(to),
    cc: people(cc),
    from: null,
  };
}

/** A reply, or a new email: forwards and new mail are "new" (nothing to answer); a compose window
 * without a compose type but in a conversation is treated as a reply. */
export function draftMode(ctx: ItemContext): "reply" | "new" {
  if (ctx.mode === "read") return "reply";
  if (ctx.composeType === "newMail" || ctx.composeType === "forward") return "new";
  return ctx.conversationId ? "reply" : "new";
}

export function insertAtCursor(text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    // setSelectedDataAsync inserts at the cursor / replaces the selection; never body.setAsync,
    // which wipes the quoted thread in new Outlook and on the web (architecture §3.2).
    Office.context.mailbox.item!.body.setSelectedDataAsync(text, { coercionType: Office.CoercionType.Text }, (r) =>
      r.status === Office.AsyncResultStatus.Succeeded ? resolve() : reject(new Error(r.error.code.toString())),
    );
  });
}

/** The text of the email being written (compose mode), for the pre-send checks. */
export function bodyText(): Promise<string> {
  return new Promise((resolve, reject) => {
    Office.context.mailbox.item!.body.getAsync(Office.CoercionType.Text, (r) =>
      r.status === Office.AsyncResultStatus.Succeeded ? resolve(r.value) : reject(new Error(r.error.code.toString())),
    );
  });
}

/** Plain text as minimal HTML for a reply form: escaped, line breaks kept. */
export function textToHtml(text: string): string {
  const escaped = text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  return `<div>${escaped.replaceAll(/\r?\n/g, "<br>")}</div>`;
}

/** Read mode: open Outlook's reply (or reply-all) form with the draft in it. */
export function openReply(text: string, all: boolean): void {
  const item = Office.context.mailbox.item as Office.MessageRead;
  const form = { htmlBody: textToHtml(text) };
  if (all) item.displayReplyAllForm(form);
  else item.displayReplyForm(form);
}
