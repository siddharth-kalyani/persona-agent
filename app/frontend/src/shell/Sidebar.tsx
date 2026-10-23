/** The sidebar: wordmark, search (opens the command palette), grouped navigation and the account
 * menu. It recedes: muted labels, no borders, the selected item marked by a neutral fill and a
 * thin accent bar. */
import {
  Avatar,
  makeStyles,
  Menu,
  MenuDivider,
  MenuGroup,
  MenuGroupHeader,
  MenuItem,
  MenuItemRadio,
  MenuList,
  MenuPopover,
  MenuTrigger,
  mergeClasses,
  tokens,
} from "@fluentui/react-components";
import { ArrowExit16Regular, ChevronUpDown16Regular, Search16Regular } from "@fluentui/react-icons";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useThemePreference, type ThemePreference } from "../theme/ThemeProvider";
import { Kbd, modKey, Pill, typo, vt } from "../ui";
import { hoverTransition } from "../theme/motion";
import { GROUP_LABELS, type Destination } from "./nav";

const useStyles = makeStyles({
  root: { display: "flex", flexDirection: "column", height: "100%", gap: "4px", padding: "12px 8px 8px" },
  top: { display: "flex", alignItems: "center", gap: "8px", padding: "4px 8px 8px", minHeight: "36px" },
  wordmark: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    ...typo.itemTitle,
    fontSize: "15px",
    fontWeight: 600,
    color: vt.text1,
    textDecoration: "none",
    flexGrow: 1,
    minWidth: 0,
  },
  search: {
    ...hoverTransition,
    display: "flex",
    alignItems: "center",
    gap: "8px",
    height: "32px",
    margin: "0 4px 8px",
    padding: "0 6px 0 10px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    color: vt.text3,
    ...typo.meta,
    cursor: "pointer",
    textAlign: "left",
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover, color: vt.text2 } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "1px" },
  },
  searchLabel: { flexGrow: 1 },
  nav: { display: "grid", gap: "2px", overflowY: "auto", flexGrow: 1, alignContent: "start", paddingBottom: "8px" },
  groupLabel: { ...typo.label, color: vt.text3, padding: "16px 10px 4px" },
  item: {
    ...hoverTransition,
    position: "relative",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    height: "32px",
    padding: "0 10px",
    borderRadius: tokens.borderRadiusMedium,
    color: vt.text2,
    textDecoration: "none",
    ...typo.itemTitle,
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.hover, color: vt.text1 } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px" },
    "@media (pointer: coarse)": { height: "44px" },
  },
  itemIcon: { fontSize: "16px", display: "grid", placeItems: "center", flexShrink: 0 },
  selected: {
    backgroundColor: vt.selected,
    color: vt.text1,
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.selected } },
    "::before": {
      content: '""',
      position: "absolute",
      left: "0",
      top: "8px",
      bottom: "8px",
      width: "3px",
      borderRadius: "0 3px 3px 0",
      backgroundColor: vt.accent,
    },
  },
  count: { marginLeft: "auto", ...typo.label, fontWeight: 400, color: vt.text2, ...typo.tabular },
  bottom: { borderTop: `1px solid ${tokens.colorNeutralStroke3}`, paddingTop: "8px" },
  account: {
    ...hoverTransition,
    display: "flex",
    alignItems: "center",
    gap: "10px",
    width: "100%",
    padding: "6px 8px",
    border: "none",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: "transparent",
    color: vt.text1,
    cursor: "pointer",
    textAlign: "left",
    font: "inherit",
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.hover } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px" },
  },
  accountText: { display: "grid", minWidth: 0, flexGrow: 1 },
  accountName: { ...typo.itemTitle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  accountMeta: { display: "flex", alignItems: "center", gap: "6px", minWidth: 0 },
  accountEmail: { ...typo.label, fontWeight: 400, color: vt.text3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 },
  accountBadge: { flexShrink: 0 },
  chevron: { color: vt.text3, flexShrink: 0 },
});

/** The Vanimo mark: the app icon's "V" on the accent, drawn inline (no image request). */
export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden focusable="false">
      <rect width="20" height="20" rx="5" fill="var(--vAccent, #007972)" />
      <path d="M5.6 5.5h2.1l2.3 6.6 2.3-6.6h2.1L11.1 14.5H8.9z" fill="#fff" />
    </svg>
  );
}

export function Sidebar({
  destinations,
  active,
  counts,
  onSearch,
  onNavigate,
  notifications,
  account,
}: {
  destinations: Destination[];
  active: string;
  counts?: Partial<Record<string, number>>;
  onSearch: () => void;
  onNavigate?: () => void;
  notifications?: ReactNode;
  account: ReactNode;
}) {
  const s = useStyles();
  const groups = (["main", "voice", "data", "admin"] as const)
    .map((g) => ({ g, items: destinations.filter((d) => d.group === g) }))
    .filter((x) => x.items.length > 0);
  return (
    <div className={s.root}>
      <div className={s.top}>
        <Link to="/" className={s.wordmark} onClick={onNavigate} aria-label="Vanimo home">
          <Mark />
          Vanimo
        </Link>
        {notifications}
      </div>
      <button type="button" className={s.search} onClick={onSearch} aria-label="Search or jump to (command palette)">
        <Search16Regular />
        <span className={s.searchLabel}>Search</span>
        <Kbd>{modKey}</Kbd>
        <Kbd>K</Kbd>
      </button>
      <nav className={s.nav} aria-label="Main">
        {groups.map(({ g, items }) => (
          <div key={g} role="group" aria-label={GROUP_LABELS[g] ?? "Main"} style={{ display: "grid", gap: 2 }}>
            {GROUP_LABELS[g] && <div className={s.groupLabel} aria-hidden>{GROUP_LABELS[g]}</div>}
            {items.map((d) => {
              const selected = d.path === active;
              const Icon = d.icon;
              const count = counts?.[d.path];
              return (
                <Link
                  key={d.path}
                  to={d.path}
                  onClick={onNavigate}
                  className={mergeClasses(s.item, selected && s.selected)}
                  aria-current={selected ? "page" : undefined}
                >
                  <span className={s.itemIcon}>
                    <Icon filled={selected} aria-hidden />
                  </span>
                  {d.label}
                  {count ? (
                    <span className={s.count} aria-label={`${count} waiting`}>
                      {count}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className={s.bottom}>{account}</div>
    </div>
  );
}

const THEMES: Array<[ThemePreference, string]> = [
  ["system", "Match system"],
  ["light", "Light"],
  ["dark", "Dark"],
];

export function AccountMenu({
  name,
  email,
  badge,
  onSignOut,
}: {
  name: string;
  email: string | null;
  badge?: string | null;
  onSignOut: () => void;
}) {
  const s = useStyles();
  const theme = useThemePreference();
  return (
    <Menu
      positioning="above-start"
      checkedValues={{ theme: [theme.preference] }}
      onCheckedValueChange={(_, d) => d.name === "theme" && theme.setPreference(d.checkedItems[0] as ThemePreference)}
    >
      <MenuTrigger disableButtonEnhancement>
        <button type="button" className={s.account} aria-label={`Account: ${name}`}>
          <Avatar name={name} size={24} color="neutral" aria-hidden />
          <span className={s.accountText}>
            <span className={s.accountName}>{name}</span>
            <span className={s.accountMeta}>
              {email && email !== name && <span className={s.accountEmail}>{email}</span>}
              {badge && <Pill className={s.accountBadge}>{badge}</Pill>}
            </span>
          </span>
          <ChevronUpDown16Regular className={s.chevron} />
        </button>
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          <MenuGroup>
            <MenuGroupHeader>Appearance</MenuGroupHeader>
            {THEMES.map(([value, label]) => (
              <MenuItemRadio key={value} name="theme" value={value}>
                {label}
              </MenuItemRadio>
            ))}
          </MenuGroup>
          <MenuDivider />
          <MenuItem icon={<ArrowExit16Regular />} onClick={onSignOut}>
            Sign out
          </MenuItem>
        </MenuList>
      </MenuPopover>
    </Menu>
  );
}
