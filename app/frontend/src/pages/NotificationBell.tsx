/** The in-app end of the notification channel (M5): counts only, never content — the same
 * notifications Teams' activity feed gets. Opening one takes you to the page it's about. The bell
 * carries a dot when something is unread; the count is in its label and the popover header. */
import {
  Button,
  makeStyles,
  mergeClasses,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  tokens,
} from "@fluentui/react-components";
import {
  Alert20Regular,
  AlertOn20Regular,
  CheckmarkCircle20Regular,
  DocumentSearch16Regular,
  PersonVoice16Regular,
  TaskListSquareLtr16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactElement } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { AppNotification } from "../api/client";
import { useApi } from "../api/context";
import { absoluteTime, hoverTransition, IconTile, Pill, relativeTime, typo, vt, type Tone } from "../ui";

const useStyles = makeStyles({
  trigger: { position: "relative", display: "inline-grid", placeItems: "center" },
  dot: {
    position: "absolute",
    top: "0",
    right: "0",
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: vt.accent,
    boxShadow: `0 0 0 2px ${vt.frame}`,
    pointerEvents: "none",
  },
  surface: { padding: 0, width: "360px", maxWidth: "calc(100vw - 24px)" },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
    padding: "10px 10px 10px 16px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
  },
  headerTitle: { display: "flex", alignItems: "center", gap: "8px" },
  title: { ...typo.cardTitle, color: vt.text1, margin: 0 },
  list: { listStyle: "none", margin: 0, padding: "6px", display: "grid", gap: "2px", maxHeight: "380px", overflowY: "auto" },
  item: {
    ...hoverTransition,
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) 8px",
    gap: "12px",
    alignItems: "start",
    width: "100%",
    padding: "10px",
    border: "none",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: "transparent",
    color: vt.text1,
    textAlign: "left",
    font: "inherit",
    cursor: "pointer",
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.hover } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px" },
  },
  unreadDot: { width: "8px", height: "8px", borderRadius: "50%", marginTop: "12px", backgroundColor: vt.accent },
  readDot: { backgroundColor: "transparent" },
  text: { display: "grid", gap: "2px", minWidth: 0 },
  unread: { ...typo.body, fontWeight: 500 },
  read: { ...typo.body, color: vt.text2 },
  when: { ...typo.meta, color: vt.text3 },
  empty: { display: "grid", justifyItems: "center", gap: "8px", ...typo.meta, color: vt.text2, padding: "28px 16px", textAlign: "center" },
  emptyIcon: { color: vt.success },
  srOnly: {
    position: "absolute",
    width: "1px",
    height: "1px",
    overflow: "hidden",
    clip: "rect(0 0 0 0)",
    whiteSpace: "nowrap",
  },
});

const TARGET: Record<AppNotification["kind"], string> = {
  commitments_due: "/commitments",
  rules_to_confirm: "/persona",
  review_reminder: "/setup",
};

const KIND: Record<AppNotification["kind"], { icon: ReactElement; tone: Tone }> = {
  commitments_due: { icon: <TaskListSquareLtr16Regular />, tone: "accent" },
  rules_to_confirm: { icon: <PersonVoice16Regular />, tone: "purple" },
  review_reminder: { icon: <DocumentSearch16Regular />, tone: "blue" },
};

export function NotificationBell() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    api.notifications().then(
      (r) => {
        setItems(r.items);
        setUnread(r.unread);
      },
      () => undefined,
    );
  }, [api]);

  useEffect(() => {
    load();
  }, [load, location.pathname]);

  async function go(n: AppNotification) {
    setOpen(false);
    await api.markNotificationsRead(n.id).catch(() => undefined);
    load();
    navigate(TARGET[n.kind]);
  }

  return (
    <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)} positioning="below-start" trapFocus>
      <PopoverTrigger disableButtonEnhancement>
        <Button
          appearance="subtle"
          icon={
            <span className={styles.trigger}>
              {unread > 0 ? <AlertOn20Regular /> : <Alert20Regular />}
              {unread > 0 && <span className={styles.dot} aria-hidden />}
            </span>
          }
          aria-label={`Notifications, ${unread} unread`}
        />
      </PopoverTrigger>
      <PopoverSurface className={styles.surface} aria-label="Notifications">
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <h2 className={styles.title}>Notifications</h2>
            {unread > 0 && <Pill tone="accent">{unread} new</Pill>}
          </div>
          {unread > 0 && (
            <Button
              size="small"
              appearance="subtle"
              onClick={() => {
                void api.markNotificationsRead().then(load, () => undefined);
              }}
            >
              Mark all read
            </Button>
          )}
        </div>
        {items.length === 0 ? (
          <div className={styles.empty}>
            <CheckmarkCircle20Regular className={styles.emptyIcon} aria-hidden />
            You're all caught up.
          </div>
        ) : (
          <ul className={styles.list}>
            {items.map((n) => (
              <li key={n.id}>
                <button type="button" className={styles.item} onClick={() => void go(n)}>
                  <IconTile icon={KIND[n.kind].icon} tone={KIND[n.kind].tone} size={32} />
                  <span className={styles.text}>
                    <span className={n.read ? styles.read : styles.unread}>{n.text}</span>
                    <span className={styles.when} title={absoluteTime(n.createdAt)}>
                      {relativeTime(n.createdAt)}
                      {!n.read && <span className={styles.srOnly}> · unread</span>}
                    </span>
                  </span>
                  <span className={mergeClasses(styles.unreadDot, n.read && styles.readDot)} aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </PopoverSurface>
    </Popover>
  );
}
