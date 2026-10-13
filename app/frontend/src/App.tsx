import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { Button, makeStyles, Tab, TabList, Text, Title2, tokens } from "@fluentui/react-components";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useConfig } from "./api/context";
import { apiScope } from "./config";
import { Diagnostics } from "./pages/Diagnostics";
import { Home } from "./pages/Home";
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
  signin: { display: "grid", gap: tokens.spacingVerticalL, justifyItems: "start", marginTop: "10vh" },
});

export function App() {
  const styles = useStyles();
  const { instance, accounts } = useMsal();
  const config = useConfig();
  const navigate = useNavigate();
  const location = useLocation();
  const isAdmin = (accounts[0]?.idTokenClaims?.roles as string[] | undefined)?.includes("Vanimo.Admin") ?? false;
  const tab = location.pathname.startsWith("/admin") ? "/admin/diagnostics" : location.pathname.startsWith("/spikes") ? "/spikes/teams" : "/";

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Title2 as="h1">Vanimo</Title2>
        <AuthenticatedTemplate>
          <TabList selectedValue={tab} onTabSelect={(_, d) => navigate(String(d.value))}>
            <Tab value="/">Home</Tab>
            {isAdmin && <Tab value="/admin/diagnostics">Diagnostics</Tab>}
            {isAdmin && <Tab value="/spikes/teams">Teams prefill test</Tab>}
          </TabList>
        </AuthenticatedTemplate>
        <span className={styles.spacer} />
        <AuthenticatedTemplate>
          <Button appearance="subtle" onClick={() => void instance.logoutRedirect()}>
            Sign out
          </Button>
        </AuthenticatedTemplate>
      </header>
      <main className={styles.main}>
        <UnauthenticatedTemplate>
          <div className={styles.signin}>
            <Text size={500}>Your writing voice and work memory, inside Outlook and Teams.</Text>
            <Button appearance="primary" onClick={() => void instance.loginRedirect({ scopes: [apiScope(config)] })}>
              Sign in with Microsoft
            </Button>
          </div>
        </UnauthenticatedTemplate>
        <AuthenticatedTemplate>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/admin/diagnostics" element={isAdmin ? <Diagnostics /> : <Navigate to="/" />} />
            <Route path="/spikes/teams" element={isAdmin ? <TeamsPrefill /> : <Navigate to="/" />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </AuthenticatedTemplate>
      </main>
    </div>
  );
}
