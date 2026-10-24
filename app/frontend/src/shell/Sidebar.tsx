/** The sidebar: workspace header, search (opens the command palette), grouped navigation and the
 * account row with a theme toggle. It recedes: muted labels and icons; the selected item is a raised
 * chip with its icon in the accent. */
import {
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
  shorthands,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowExit16Regular,
  ChevronUpDown16Regular,
  DesktopMac16Regular,
  Search16Regular,
  WeatherMoon16Regular,
  WeatherMoon20Regular,
  WeatherSunny16Regular,
  WeatherSunny20Regular,
} from "@fluentui/react-icons";
import type { ReactElement, ReactNode } from "react";
import { Link } from "react-router-dom";
import { useThemePreference, type ThemePreference } from "../theme/ThemeProvider";
import { IconAction, Kbd, modKey, PersonAvatar, typo, vt } from "../ui";
import { hoverTransition } from "../theme/motion";
import { GROUP_LABELS, type Destination } from "./nav";

const useStyles = makeStyles({
  root: { display: "flex", flexDirection: "column", height: "100%", gap: "4px", padding: "14px 10px 10px" },
  top: { display: "flex", alignItems: "center", gap: "8px", padding: "2px 4px 10px 6px", minHeight: "40px" },
  wordmark: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    color: vt.text1,
    textDecoration: "none",
    flexGrow: 1,
    minWidth: 0,
    borderRadius: tokens.borderRadiusMedium,
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "2px" },
  },
  wordmarkText: { display: "grid", minWidth: 0 },
  wordmarkName: { ...typo.cardTitle, fontSize: "15px", letterSpacing: "-0.015em" },
  wordmarkSub: { ...typo.label, fontWeight: 400, color: vt.text3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  search: {
    ...hoverTransition,
    display: "flex",
    alignItems: "center",
    gap: "8px",
    height: "34px",
    margin: "0 2px 10px",
    padding: "0 6px 0 10px",
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: vt.card,
    boxShadow: vt.shadowButton,
    color: vt.text3,
    ...typo.meta,
    cursor: "pointer",
    textAlign: "left",
    "@media (hover: hover)": { ":hover": { ...shorthands.borderColor(vt.borderStrong), color: vt.text2 } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "1px" },
  },
  searchLabel: { flexGrow: 1 },
  nav: { display: "grid", gap: "2px", overflowY: "auto", flexGrow: 1, alignContent: "start", padding: "0 2px 8px" },
  group: { display: "grid", gap: "1px" },
  groupLabel: { ...typo.label, color: vt.text3, padding: "18px 10px 6px" },
  item: {
    ...hoverTransition,
    position: "relative",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    height: "34px",
    padding: "0 10px",
    borderRadius: tokens.borderRadiusMedium,
    color: vt.text2,
    textDecoration: "none",
    ...typo.itemTitle,
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.hover, color: vt.text1 } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px" },
    "@media (pointer: coarse)": { height: "44px" },
  },
  itemIcon: { display: "grid", placeItems: "center", flexShrink: 0, color: vt.text3 },
  selected: {
    backgroundColor: vt.card,
    color: vt.text1,
    boxShadow: `0 0 0 1px ${vt.border}, ${vt.shadowButton}`,
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.card } },
  },
  selectedIcon: { color: vt.accent },
  count: {
    marginLeft: "auto",
    minWidth: "20px",
    height: "20px",
    padding: "0 6px",
    borderRadius: "999px",
    display: "inline-grid",
    placeItems: "center",
    ...typo.label,
    ...typo.tabular,
    backgroundColor: vt.accentTint,
    color: vt.accentTintText,
  },
  bottom: { display: "flex", alignItems: "center", gap: "4px", borderTop: `1px solid ${vt.border}`, paddingTop: "10px" },
  account: {
    ...hoverTransition,
    display: "flex",
    alignItems: "center",
    gap: "10px",
    flexGrow: 1,
    minWidth: 0,
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
  accountMeta: { ...typo.label, fontWeight: 400, color: vt.text3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 },
  chevron: { color: vt.text3, flexShrink: 0 },
});

/** The Vanimo mark: the app icon's "V" on the brand colour, drawn inline (no image request). */
export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden focusable="false">
      <rect width="20" height="20" rx="5.5" fill="var(--colorBrandBackground, #00756E)" />
      <path d="M5.6 5.5h2.1l2.3 6.6 2.3-6.6h2.1L11.1 14.5H8.9z" fill="#fff" />
    </svg>
  );
}

export function Sidebar({
  destinations,
  active,
  counts,
  workspace,
  onSearch,
  onNavigate,
  notifications,
  account,
}: {
  destinations: Destination[];
  active: string;
  counts?: Partial<Record<string, number>>;
  /** The line under the wordmark: "Sample workspace" or "Microsoft 365". */
  workspace?: string;
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
        <Link to="/" className={s.wordmark} onClick={onNavigate} aria-label={workspace ? `Vanimo home, ${workspace}` : "Vanimo home"}>
          <Mark size={30} />
          <span className={s.wordmarkText}>
            <span className={s.wordmarkName}>Vanimo</span>
            {workspace && <span className={s.wordmarkSub}>{workspace}</span>}
          </span>
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
          <div key={g} role="group" aria-label={GROUP_LABELS[g] ?? "Main"} className={s.group}>
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
                  <span className={mergeClasses(s.itemIcon, selected && s.selectedIcon)}>
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
      <div className={s.bottom}>
        {account}
        <ThemeToggle />
      </div>
    </div>
  );
}

/** One click between light and dark (the account menu also offers "Match system"). */
function ThemeToggle() {
  const theme = useThemePreference();
  const next = theme.mode === "dark" ? "light" : "dark";
  return (
    <IconAction
      icon={theme.mode === "dark" ? <WeatherSunny20Regular /> : <WeatherMoon20Regular />}
      label={next === "dark" ? "Switch to dark theme" : "Switch to light theme"}
      size="medium"
      onClick={() => theme.setPreference(next)}
    />
  );
}

const THEMES: Array<[ThemePreference, string, ReactElement]> = [
  ["system", "Match system", <DesktopMac16Regular key="s" />],
  ["light", "Light", <WeatherSunny16Regular key="l" />],
  ["dark", "Dark", <WeatherMoon16Regular key="d" />],
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
  // The role under the name; the address (which would only truncate here) heads the menu.
  const meta = badge ?? (email && email !== name ? email : null);
  return (
    <Menu
      positioning="above-start"
      checkedValues={{ theme: [theme.preference] }}
      onCheckedValueChange={(_, d) => d.name === "theme" && theme.setPreference(d.checkedItems[0] as ThemePreference)}
    >
      <MenuTrigger disableButtonEnhancement>
        <button type="button" className={s.account} aria-label={`Account: ${name}`}>
          <PersonAvatar name={name} id={email} size={28} />
          <span className={s.accountText}>
            <span className={s.accountName}>{name}</span>
            {meta && <span className={s.accountMeta}>{meta}</span>}
          </span>
          <ChevronUpDown16Regular className={s.chevron} />
        </button>
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          {email && (
            <>
              <MenuGroupHeader>{email}</MenuGroupHeader>
              <MenuDivider />
            </>
          )}
          <MenuGroup>
            <MenuGroupHeader>Appearance</MenuGroupHeader>
            {THEMES.map(([value, label, icon]) => (
              <MenuItemRadio key={value} name="theme" value={value} icon={icon}>
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
