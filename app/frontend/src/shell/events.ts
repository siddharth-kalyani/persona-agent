/** Window events the shell listens for. */

/** The signed-in user's profile changed (e.g. an admin resumed a paused organisation): the shell
 * re-reads it at once instead of waiting for the next navigation. */
export const ME_CHANGED = "vanimo:me-changed";

export function announceMeChanged(): void {
  window.dispatchEvent(new Event(ME_CHANGED));
}
