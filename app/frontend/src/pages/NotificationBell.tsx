/** The in-app end of the notification channel (M5): counts only, never content — the same
 * notifications Teams' activity feed gets. Opening one takes you to the page it's about. */
import {
  Button,
  makeStyles,
  mergeClasses,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  tokens,
} from "@fluentui/react-components";
import { Alert20Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { AppNotification } from "../api/client";
import { useApi } from "../api/context";
import { absoluteTime, hoverTransition, relativeTime, typo, vt } from "../ui";

const useStyles = makeStyles({
  trigger: { position: "relative" },
  count: {
    position: "absolute",
    top: "2px",
    right: "1px",
    minWidth: "16px",
    height: "16px",
    padding: "0 4px",
    borderRadius: "8px",
    backgroundColor: vt.accent,
    color: tokens.colorNeutralForegroundOnBrand,
    fontSize: "10px",
    fontWeight: 600,
    lineHeight: "16px",
    textAlign: "center",
    ...typo.tabular,
    boxShadow: `0 0 0 2px ${tokens.colorNeutralBackground2}`,
    pointerEvents: "none",
  },
  surface: { padding: 0, width: "340px", maxWidth: "calc(100vw - 24px)" },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 12px 10px 16px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  title: { ...typo.itemTitle, color: vt.text1, margin: 0 },
  list: { listStyle: "none", margin: 0, padding: "4px", display: "grid", gap: "2px", maxHeight: "360px", overflowY: "auto" },
  item: {
    ...hoverTransition,
    display: "grid",
    gridTemplateColumns: "8px minmax(0, 1fr)",
    gap: "10px",
    alignItems: "start",
    width: "100%",
    padding: "8px 10px",
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
  unreadDot: { width: "8px", height: "8px", borderRadius: "50%", marginTop: "6px", backgroundColor: vt.accent },
  readDot: { backgroundColor: "transparent" },
  text: { display: "grid", gap: "2px", minWidth: 0 },
  unread: { ...typo.body, fontWeight: 500 },
  read: { ...typo.body, color: vt.text2 },
  when: { ...typo.meta, color: vt.text3 },
  empty: { ...typo.meta, color: vt.text2, padding: "20px 16px" },
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
          size="small"
          className={styles.trigger}
          icon={<Alert20Regular />}
          aria-label={`Notifications, ${unread} unread`}
        >
          {unread > 0 && (
            <span className={styles.count} aria-hidden>
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverSurface className={styles.surface} aria-label="Notifications">
        <div className={styles.header}>
          <h2 className={styles.title}>Notifications</h2>
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
          <div className={styles.empty}>Nothing new.</div>
        ) : (
          <ul className={styles.list}>
            {items.map((n) => (
              <li key={n.id}>
                <button type="button" className={styles.item} onClick={() => void go(n)}>
                  <span className={mergeClasses(styles.unreadDot, n.read && styles.readDot)} aria-hidden />
                  <span className={styles.text}>
                    <span className={n.read ? styles.read : styles.unread}>{n.text}</span>
                    <span className={styles.when} title={absoluteTime(n.createdAt)}>
                      {relativeTime(n.createdAt)}
                      {!n.read && <span className={styles.srOnly}> · unread</span>}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </PopoverSurface>
    </Popover>
  );
}
