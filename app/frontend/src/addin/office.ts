/// <reference types="office-js" />
/** Office.js helpers for the Outlook task pane (kept free of React so they're cheap to test). */

export const HELLO_TEXT = "Hello from Vanimo — inserted at your cursor.";

export interface ItemContext {
  mode: "compose" | "read";
  composeType: string | null; // newMail | reply | forward (Mailbox 1.10+)
  recipients: number | null;
  hasConversationId: boolean;
}

function asyncValue<T>(fn: (cb: (r: Office.AsyncResult<T>) => void) => void): Promise<T | null> {
  return new Promise((resolve) => fn((r) => resolve(r.status === Office.AsyncResultStatus.Succeeded ? r.value : null)));
}

/** Metadata the drafting surface will need in M3 — counts and types only, never names or text. */
export async function readItemContext(item: Office.MessageCompose | Office.MessageRead): Promise<ItemContext> {
  // In read mode `subject` is a string; in compose mode it is an object with getAsync/setAsync.
  if (typeof (item as { subject?: unknown }).subject === "string") {
    const read = item as Office.MessageRead;
    return {
      mode: "read",
      composeType: null,
      recipients: (read.to?.length ?? 0) + (read.cc?.length ?? 0),
      hasConversationId: !!read.conversationId,
    };
  }
  const compose = item as Office.MessageCompose;
  const [to, cc] = await Promise.all([
    asyncValue<Office.EmailAddressDetails[]>((cb) => compose.to.getAsync(cb)),
    asyncValue<Office.EmailAddressDetails[]>((cb) => compose.cc.getAsync(cb)),
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
    recipients: to === null && cc === null ? null : (to?.length ?? 0) + (cc?.length ?? 0),
    hasConversationId: !!compose.conversationId,
  };
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
