import { useState } from "react";
import {
  TextInput,
  Button,
  Paper,
  Title,
  PasswordInput,
  Text,
  Stack,
  Box,
  Group,
  Divider,
  ThemeIcon,
} from "@mantine/core";
import { IconRobot } from "@tabler/icons-react";
import { AxiosError } from "axios";
import { loginRequest } from "../api/auth";
import { useAuth } from "../auth/useAuth";

import classes from "../assets/styles/LoginPage.module.css";

export default function LoginPage() {
  const { login } = useAuth();

  const [email, setEmail] = useState("alice@example.com");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setError(null);
    setLoading(true);

    try {
      const data = await loginRequest({ email, password });
      login(data.access_token);
    } catch (err: unknown) {
      let message = "Login failed";

      if (err instanceof AxiosError) {
        const data = err.response?.data as
          | { detail?: string }
          | { detail?: { loc: (string | number)[]; msg: string }[] }
          | undefined;

        if (typeof data?.detail === "string") {
          message = data.detail;
        } else if (Array.isArray(data?.detail)) {
          message = data.detail
            .map((e) => `${e.loc.join(".")}: ${e.msg}`)
            .join(" | ");
        } else {
          message = err.message ?? message;
        }
      } else if (err instanceof Error) {
        message = err.message;
      }

      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box className={classes.root}>
      {/* <Box className={classes.left} /> */}
      <Box className={classes.left} aria-hidden>
        <div className={classes.scanlines} />
        <div className={classes.noise} />

        <div className={classes.terminal}>
          <div className={classes.terminalTop}>
            <span className={classes.dotRed} />
            <span className={classes.dotYellow} />
            <span className={classes.dotGreen} />
            <span className={classes.terminalTitle}>rbac-mcp-agent</span>
          </div>

          <div className={classes.terminalBodyWrap}>
            <div className={classes.caretSweep} />
            <pre className={classes.terminalBody}>
              {`$ mcp connect http://localhost:8001/mcp
✔ tools discovered: 11
$ auth login alice@example.com
✔ session issued (jwt)
$ agent run "what's the weather in prague?"
… thinking
✔ tool: weather_now(city="Prague")
→ 2°C, light snow
`}
              <span className={classes.cursor}>█</span>
            </pre>
          </div>

        </div>
      </Box>




      <Box className={classes.right}>
        <Paper className={classes.card} p="xl" radius="lg" withBorder>
          <Box
            component="form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!loading) void submit();
            }}
          >
            <Stack gap="lg">
              {/* Brand-ish header (TopBar vibe, but local to page) */}
              <Group gap="md" wrap="nowrap" className={classes.brandRow}>
                <ThemeIcon
                  size={44}
                  radius={12}
                  variant="transparent"
                  styles={{
                    root: {
                      background:
                        "linear-gradient(135deg, var(--mantine-color-green-7), var(--mantine-color-teal-4))",
                      boxShadow: "0 8px 22px rgba(0, 0, 0, 0.10)",
                      display: "grid",
                      placeItems: "center",
                    },
                  }}
                >
                  <IconRobot size={26} color="white" />
                </ThemeIcon>

                <Box style={{ minWidth: 0 }}>
                  <Title order={3} className={classes.brandTitle}>
                    RBAC MCP Agent
                  </Title>
                  <Text size="sm" c="dimmed" className={classes.brandSubtitle}>
                    Sign in to continue
                  </Text>
                </Box>
              </Group>

              <Divider />

              <Stack gap="md">
                <TextInput
                  label="Email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.currentTarget.value)}
                  autoComplete="email"
                  disabled={loading}
                  radius="md"
                />

                <PasswordInput
                  label="Password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.currentTarget.value)}
                  autoComplete="current-password"
                  disabled={loading}
                  radius="md"
                />

                <Button
                  fullWidth
                  type="submit"
                  loading={loading}
                  radius="md"
                  className={classes.loginButton}
                  color="teal"
                >
                  Login
                </Button>

                {error && (
                  <Text c="red" size="sm" className={classes.errorText}>
                    {error}
                  </Text>
                )}
              </Stack>

            </Stack>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
}
