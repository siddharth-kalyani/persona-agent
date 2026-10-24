/** The app shell: a receding sidebar on the tinted frame and the page on a lighter inset panel
 * (≥1024px); a top bar with a navigation drawer below that. Ctrl/⌘ K opens the command palette
 * everywhere. Only the page area fades on navigation (150 ms); nothing else moves. */
import {
  Button,
  DrawerBody,
  makeStyles,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  OverlayDrawer,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowExit16Regular,
  Compose16Regular,
  DesktopMac16Regular,
  Navigation20Regular,
  Search20Regular,
  WeatherMoon16Regular,
  WeatherSunny16Regular,
} from "@fluentui/react-icons";
import { startTransition, useEffect, useMemo, useRef, useState, ViewTransition } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import type { Me } from "./api/client";
import { useApi } from "./api/context";
import { useAuth } from "./auth/session";
import { Backstops } from "./pages/admin/Backstops";
import { ClientScoping } from "./pages/admin/ClientScoping";
import { Commitments } from "./pages/commitments/Commitments";
import { ChangePassword } from "./pages/ChangePassword";
import { Learning } from "./pages/learning/Learning";
import { Meetings } from "./pages/meetings/Meetings";
import { Persona } from "./pages/learning/Persona";
import { MyData } from "./pages/controls/MyData";
import { Setup } from "./pages/controls/Setup";
import { Diagnostics } from "./pages/Diagnostics";
import { Draft } from "./pages/drafting/Draft";
import { Queue } from "./pages/drafting/Queue";
import { Home } from "./pages/Home";
import { NotificationBell } from "./pages/NotificationBell";
import { SampleWorkspace } from "./pages/sample/SampleWorkspace";
import { SignIn } from "./pages/SignIn";
import { TeamsPrefill } from "./pages/TeamsPrefill";
import { CommandPalette, type Command } from "./shell/CommandPalette";
import { activePath, visibleDestinations } from "./shell/nav";
import { AccountMenu, Mark, Sidebar } from "./shell/Sidebar";
import { useThemePreference } from "./theme/ThemeProvider";
import { isMod, PageIconContext, typo, vt } from "./ui";
import { ME_CHANGED } from "./shell/events";

const useStyles = makeStyles({
  shell: {
    display: "grid",
    gridTemplateColumns: "248px minmax(0, 1fr)",
    minHeight: "100vh",
    backgroundColor: vt.frame,
    "@media (max-width: 1023px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  sidebar: {
    position: "sticky",
    top: 0,
    height: "100vh",
    "@media (max-width: 1023px)": { display: "none" },
  },
  topbar: {
    display: "none",
    "@media (max-width: 1023px)": {
      display: "flex",
      alignItems: "center",
      gap: "8px",
      height: "52px",
      padding: "0 8px",
      position: "sticky",
      top: 0,
      zIndex: 10,
      backgroundColor: vt.frame,
      borderBottom: `1px solid ${vt.border}`,
    },
  },
  topTitle: { ...typo.cardTitle, fontSize: "15px", flexGrow: 1, display: "flex", alignItems: "center", gap: "10px" },
  panel: {
    margin: "8px 8px 8px 0",
    backgroundColor: vt.surface,
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    boxShadow: vt.shadowCard,
    minHeight: "calc(100vh - 16px)",
    minWidth: 0,
    "@media (max-width: 1023px)": { margin: 0, border: "none", borderRadius: 0, boxShadow: "none", minHeight: "calc(100vh - 52px)" },
  },
  content: {
    padding: "32px 40px 72px",
    "@media (max-width: 1279px)": { padding: "28px 32px 64px" },
    "@media (max-width: 1023px)": { padding: "20px 24px 48px" },
    "@media (max-width: 639px)": { padding: "16px 16px 40px" },
  },
  // One centred column: every page starts at the same left edge, whatever its own width.
  column: { maxWidth: "1280px", marginInline: "auto" },
  banner: { marginBottom: "24px" },
  skip: {
    position: "absolute",
    left: "8px",
    top: "-40px",
    zIndex: 100,
    padding: "8px 12px",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    color: vt.text1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    ":focus": { top: "8px" },
  },
  drawer: { width: "288px", backgroundColor: vt.frame },
  drawerBody: { padding: 0 },
  auth: { minHeight: "100vh", backgroundColor: vt.frame, display: "grid", placeItems: "start center", padding: "12vh 16px 48px" },
});

/** True below the sidebar breakpoint (the shell switches to a top bar and a drawer). */
function useNarrow(): boolean {
  const query = "(max-width: 1023px)";
  const [narrow, setNarrow] = useState(() => window.matchMedia?.(query).matches === true);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const onChange = () => setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return narrow;
}

/** The signed-in user's profile once, for the shell (data source, name, organisation pause). */
function useMe(ready: boolean, pathname: string): Me | null {
  const api = useApi();
  const [me, setMe] = useState<Me | null>(null);
  const [nudge, setNudge] = useState(0);
  const lastRead = useRef(0);
  useEffect(() => {
    const onChange = () => setNudge((n) => n + 1);
    window.addEventListener(ME_CHANGED, onChange);
    return () => window.removeEventListener(ME_CHANGED, onChange);
  }, []);
  useEffect(() => {
    if (!ready) return;
    lastRead.current = 0;
  }, [ready, nudge]);
  useEffect(() => {
    if (!ready || Date.now() - lastRead.current < 30_000) return;
    lastRead.current = Date.now();
    let live = true;
    api.me().then(
      (m) => live && setMe(m),
      () => live && setMe(null),
    );
    return () => {
      live = false;
    };
  }, [api, ready, pathname, nudge]);
  return me;
}

export function App() {
  const styles = useStyles();
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useThemePreference();
  const ready = auth.signedIn && !auth.mustChangePassword;
  const me = useMe(ready, location.pathname);
  const [palette, setPalette] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const narrow = useNarrow();

  const destinations = useMemo(
    () => visibleDestinations({ isAdmin: auth.isAdmin, sample: me?.dataSource === "sample" }),
    [auth.isAdmin, me?.dataSource],
  );
  const active = activePath(location.pathname);
  const go = (path: string) => startTransition(() => void navigate(path));

  useEffect(() => {
    if (!ready) return;
    const onKey = (e: KeyboardEvent) => {
      if (isMod(e, "k")) {
        e.preventDefault();
        setPalette((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ready]);

  const commands = useMemo<Command[]>(() => {
    const nav: Command[] = destinations.map((d) => {
      const Icon = d.icon;
      return { id: `go${d.path}`, label: d.label, group: "Go to", icon: <Icon />, aliases: d.aliases, run: () => go(d.path) };
    });
    const actions: Command[] = [
      { id: "new-email", label: "Write a new email", group: "Actions", icon: <Compose16Regular />, aliases: ["draft", "compose"], run: () => go("/draft") },
      { id: "theme-light", label: "Use light theme", group: "Actions", icon: <WeatherSunny16Regular />, aliases: ["appearance", "mode"], run: () => theme.setPreference("light") },
      { id: "theme-dark", label: "Use dark theme", group: "Actions", icon: <WeatherMoon16Regular />, aliases: ["appearance", "mode", "night"], run: () => theme.setPreference("dark") },
      { id: "theme-system", label: "Match system theme", group: "Actions", icon: <DesktopMac16Regular />, aliases: ["appearance", "auto"], run: () => theme.setPreference("system") },
      { id: "sign-out", label: "Sign out", group: "Actions", icon: <ArrowExit16Regular />, aliases: ["log out", "exit"], run: () => void auth.signOut() },
    ]; // prettier-ignore
    return [...nav, ...actions];
  }, [destinations, theme.setPreference, auth.signOut]);

  if (!auth.signedIn || auth.mustChangePassword) {
    return <div className={styles.auth}>{!auth.signedIn ? <SignIn /> : <ChangePassword />}</div>;
  }

  const name = me?.user.displayName ?? auth.email ?? "You";
  const badge = auth.roles.includes("Vanimo.SuperAdmin") ? "Super-admin" : auth.isAdmin ? "Admin" : null;
  const sidebar = (onNavigate?: () => void, bell = true) => (
    <Sidebar
      destinations={destinations}
      active={active}
      onSearch={() => {
        setDrawer(false);
        setPalette(true);
      }}
      onNavigate={onNavigate}
      workspace={me ? (me.dataSource === "sample" ? "Sample workspace" : "Microsoft 365") : undefined}
      notifications={bell ? <NotificationBell /> : undefined}
      account={<AccountMenu name={name} email={auth.email} badge={badge} onSignOut={() => void auth.signOut()} />}
    />
  );
  // Animate between sections only (not between a page's own states).
  const section = location.pathname.split("/").slice(0, active.startsWith("/admin") ? 3 : 2).join("/") || "/";
  const ActiveIcon = destinations.find((d) => d.path === active)?.icon;

  return (
    <div className={styles.shell}>
      <a href="#main" className={styles.skip}>
        Skip to content
      </a>
      <aside className={styles.sidebar} aria-label="Sidebar">
        {!narrow && sidebar()}
      </aside>
      <div style={{ minWidth: 0 }}>
        <div className={styles.topbar}>
          <Button appearance="subtle" icon={<Navigation20Regular />} aria-label="Open navigation" onClick={() => setDrawer(true)} />
          <span className={styles.topTitle}>
            <Mark size={24} />
            Vanimo
          </span>
          {narrow && <NotificationBell />}
          <Button appearance="subtle" icon={<Search20Regular />} aria-label="Search or jump to" onClick={() => setPalette(true)} />
        </div>
        <OverlayDrawer
          open={drawer}
          onOpenChange={(_, d) => setDrawer(d.open)}
          className={styles.drawer}
          position="start"
          aria-label="Navigation"
        >
          <DrawerBody className={styles.drawerBody}>{sidebar(() => setDrawer(false), false)}</DrawerBody>
        </OverlayDrawer>
        <main id="main" className={styles.panel} tabIndex={-1}>
          <div className={styles.content}>
            <div className={styles.column}>
            {me?.pipelinePaused && (
              <MessageBar intent="warning" className={styles.banner}>
                <MessageBarBody>
                  <MessageBarTitle>Paused for your organisation</MessageBarTitle>
                  A sensitive-data check found something an admin needs to review. Nothing new is read, learned or drafted
                  until it's resumed; your settings and data controls still work.
                </MessageBarBody>
              </MessageBar>
            )}
            <ViewTransition key={section} default="none" enter="vt-page-in" exit="vt-page-out">
              <PageIconContext value={ActiveIcon ? <ActiveIcon /> : null}>
                <div>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/setup" element={<Setup />} />
                  <Route path="/controls" element={<MyData />} />
                  <Route path="/sample" element={<SampleWorkspace />} />
                  <Route path="/learning" element={<Learning />} />
                  <Route path="/persona" element={<Persona />} />
                  <Route path="/draft" element={<Draft />} />
                  <Route path="/queue" element={<Queue />} />
                  <Route path="/commitments" element={<CommitmentsPage />} />
                  <Route path="/meetings" element={<Meetings />} />
                  <Route path="/admin/scoping" element={auth.isAdmin ? <ClientScoping /> : <Navigate to="/" />} />
                  <Route path="/admin/backstops" element={auth.isAdmin ? <Backstops /> : <Navigate to="/" />} />
                  <Route path="/admin/diagnostics" element={auth.isAdmin ? <Diagnostics /> : <Navigate to="/" />} />
                  <Route path="/spikes/teams" element={auth.isAdmin ? <TeamsPrefill /> : <Navigate to="/" />} />
                  <Route path="*" element={<Navigate to="/" />} />
                </Routes>
                </div>
              </PageIconContext>
            </ViewTransition>
            </div>
          </div>
        </main>
      </div>
      <CommandPalette open={palette} onOpenChange={setPalette} commands={commands} />
    </div>
  );
}

/** The web page: "Open in Teams with this text" only if the organisation turned prefill on. */
function CommitmentsPage() {
  const api = useApi();
  const [prefill, setPrefill] = useState(false);
  useEffect(() => {
    api.teamsConfig().then((c) => setPrefill(c.prefill), () => setPrefill(false));
  }, [api]);
  return <Commitments prefill={prefill} />;
}
