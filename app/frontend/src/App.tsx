import { Badge, Button, Caption1, makeStyles, Tab, TabList, Title2, tokens } from "@fluentui/react-components";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth/session";
import { ChangePassword } from "./pages/ChangePassword";
import { Diagnostics } from "./pages/Diagnostics";
import { Home } from "./pages/Home";
import { SignIn } from "./pages/SignIn";
import { TeamsPrefill } from "./pages/TeamsPrefill";

const useStyles = makeStyles({
  shell: { minHeight: "100vh", backgroundColor: tokens.colorNeutralBackground2 },
  header: {
    display: "flex",
    alignItems: "center",
    gap: tokens.spacingHorizontalL,
    padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalXL}`,
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexWrap: "wrap",
  },
  spacer: { flexGrow: 1 },
  main: { maxWidth: "1040px", margin: "0 auto", padding: tokens.spacingHorizontalXL },
});

export function App() {
  const styles = useStyles();
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const ready = auth.signedIn && !auth.mustChangePassword;
  const tab = location.pathname.startsWith("/admin")
    ? "/admin/diagnostics"
    : location.pathname.startsWith("/spikes")
      ? "/spikes/teams"
      : "/";

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Title2 as="h1">Vanimo</Title2>
        {ready && (
          <TabList selectedValue={tab} onTabSelect={(_, d) => navigate(String(d.value))}>
            <Tab value="/">Home</Tab>
            {auth.isAdmin && <Tab value="/admin/diagnostics">Diagnostics</Tab>}
            {auth.isAdmin && <Tab value="/spikes/teams">Teams prefill test</Tab>}
          </TabList>
        )}
        <span className={styles.spacer} />
        {auth.signedIn && (
          <>
            {auth.roles.includes("Vanimo.SuperAdmin") && <Badge appearance="tint">Super-admin</Badge>}
            <Caption1>{auth.email}</Caption1>
            <Button appearance="subtle" onClick={() => void auth.signOut()}>
              Sign out
            </Button>
          </>
        )}
      </header>
      <main className={styles.main}>
        {!auth.signedIn ? (
          <SignIn />
        ) : auth.mustChangePassword ? (
          <ChangePassword />
        ) : (
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/admin/diagnostics" element={auth.isAdmin ? <Diagnostics /> : <Navigate to="/" />} />
            <Route path="/spikes/teams" element={auth.isAdmin ? <TeamsPrefill /> : <Navigate to="/" />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        )}
      </main>
    </div>
  );
}
