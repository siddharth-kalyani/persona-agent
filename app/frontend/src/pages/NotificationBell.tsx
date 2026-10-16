/** The in-app end of the notification channel (M5): counts only, never content — the same
 * notifications Teams' activity feed gets. Opening one takes you to the page it's about. */
import {
  Button,
  Caption1,
  CounterBadge,
  makeStyles,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  Text,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { AppNotification } from "../api/client";
import { useApi } from "../api/context";

const useStyles = makeStyles({
  list: { display: "grid", gap: tokens.spacingVerticalS, minWidth: "260px", maxWidth: "340px" },
  item: { justifyContent: "flex-start", textAlign: "left", height: "auto" },
  muted: { color: tokens.colorNeutralForeground3 },
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
    <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)} positioning="below-end">
      <PopoverTrigger disableButtonEnhancement>
        <Button appearance="subtle" aria-label={`Notifications, ${unread} unread`}>
          Notifications {unread > 0 && <CounterBadge count={unread} size="small" color="danger" />}
        </Button>
      </PopoverTrigger>
      <PopoverSurface>
        <div className={styles.list}>
          {items.length === 0 && <Caption1>Nothing new.</Caption1>}
          {items.map((n) => (
            <Button key={n.id} className={styles.item} appearance="subtle" onClick={() => void go(n)}>
              <span>
                <Text weight={n.read ? "regular" : "semibold"}>{n.text}</Text>
                <br />
                <Caption1 className={styles.muted}>{new Date(n.createdAt).toLocaleString()}</Caption1>
              </span>
            </Button>
          ))}
          {unread > 0 && (
            <Button
              size="small"
              onClick={() => {
                void api.markNotificationsRead().then(load, () => undefined);
              }}
            >
              Mark all read
            </Button>
          )}
        </div>
      </PopoverSurface>
    </Popover>
  );
}
