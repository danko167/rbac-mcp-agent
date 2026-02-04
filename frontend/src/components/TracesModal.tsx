import { useEffect, useMemo, useState } from "react";
import {
  Accordion,
  Alert,
  Badge,
  Box,
  Button,
  CopyButton,
  Divider,
  Group,
  Loader,
  Modal,
  Paper,
  ScrollArea,
  Stack,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconAlertCircle, IconCheck, IconCopy } from "@tabler/icons-react";
import api from "../api/client";

type ToolCall = {
  tool: string;
  args: string;
  created_at?: string;
};

type RunMeta = {
  id?: number;
  user_id?: number;
  prompt: string;
  created_at?: string;
  status?: "ok" | "error" | string;
  error?: string | null;
  final_output?: string | null;
};

type RunDetailsResponse = {
  run: RunMeta | string; // current BE: prompt string; future: run object
  tools: ToolCall[];
  final_output?: string | null; // current BE: top-level
};

type Props = {
  opened: boolean;
  onClose: () => void;
  runId: number | null;
  buildUrl: (runId: number) => string;
  title?: string;
};

function safePrettyJson(input: string): { ok: boolean; text: string } {
  if (!input) return { ok: true, text: "" };
  try {
    const parsed: unknown = JSON.parse(input);
    return { ok: true, text: JSON.stringify(parsed, null, 2) };
  } catch {
    return { ok: false, text: input };
  }
}

function formatTimestamp(ts?: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString();
}

export default function RunDetailsModal({
  opened,
  onClose,
  runId,
  buildUrl,
  title = "Run details",
}: Props) {
  const [loading, setLoading] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [data, setData] = useState<RunDetailsResponse | null>(null);

  useEffect(() => {
    if (!opened || !runId) return;

    let cancelled = false;

    (async () => {
      // Put state updates inside the async callback to avoid "sync setState in effect" warnings
      setLoading(true);
      setErrMsg(null);
      setData(null);

      try {
        const res = await api.get<RunDetailsResponse>(buildUrl(runId));
        if (cancelled) return;
        setData(res.data);
      } catch (e: unknown) {
        if (cancelled) return;

        // keep this narrow to avoid `any` linting
        const maybeErr = e as { response?: { data?: { detail?: string } } };
        setErrMsg(maybeErr?.response?.data?.detail ?? "Failed to load run details");
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [opened, runId, buildUrl]);

  // Normalize to a RunMeta object regardless of backend response shape
  const runMeta: RunMeta | null = useMemo(() => {
    if (!data) return null;

    if (typeof data.run === "string") {
      return {
        prompt: data.run,
        final_output: data.final_output ?? null,
      };
    }

    return {
      ...data.run,
      // prefer nested final_output, else fall back to top-level
      final_output: data.run.final_output ?? data.final_output ?? null,
    };
  }, [data]);

  // Avoid "data possibly null" in JSX
  const tools = data?.tools ?? [];

  const status = runMeta?.status ?? "ok";
  const statusColor = status === "error" ? "red" : "teal";

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Title order={4}>{title}</Title>}
      size="xl"
      radius="md"
      overlayProps={{ blur: 2 }}
    >
      {loading ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : errMsg ? (
        <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error">
          {errMsg}
        </Alert>
      ) : !runMeta ? (
        <Text size="sm" c="dimmed">
          No data.
        </Text>
      ) : (
        <Stack gap="sm">
          {/* Meta */}
          <Group justify="space-between" align="center">
            <Group gap="xs">
              {typeof runMeta.id === "number" ? (
                <Text size="sm" c="dimmed">
                  Run #{runMeta.id}
                </Text>
              ) : null}

              {typeof runMeta.user_id === "number" ? (
                <Text size="sm" c="dimmed">
                  User: {runMeta.user_id}
                </Text>
              ) : null}

              <Badge color={statusColor} variant="light">
                {String(status).toUpperCase()}
              </Badge>

              {runMeta.created_at ? (
                <Text size="sm" c="dimmed">
                  {formatTimestamp(runMeta.created_at)}
                </Text>
              ) : null}
            </Group>

            <CopyButton value={runMeta.prompt ?? ""} timeout={1200}>
              {({ copied, copy }) => (
                <Tooltip label={copied ? "Copied" : "Copy prompt"} withArrow>
                  <Button
                    variant="light"
                    color="teal"
                    size="xs"
                    onClick={copy}
                    leftSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                  >
                    {copied ? "Copied" : "Copy prompt"}
                  </Button>
                </Tooltip>
              )}
            </CopyButton>
          </Group>

          {runMeta.error ? (
            <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error details">
              <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                {runMeta.error}
              </Text>
            </Alert>
          ) : null}

          <Divider />

          {/* Prompt */}
          <Box>
            <Text size="sm" fw={600} mb={6}>
              Prompt
            </Text>
            <Paper withBorder radius="md" p="sm">
              <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                {runMeta.prompt}
              </Text>
            </Paper>
          </Box>

          {/* Final output */}
          <Box>
            <Group justify="space-between" align="center" mb={6}>
              <Text size="sm" fw={600}>
                Final output
              </Text>

              <CopyButton value={runMeta.final_output ?? ""} timeout={1200}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? "Copied" : "Copy output"} withArrow>
                    <Button
                      variant="subtle"
                      color="teal"
                      size="xs"
                      onClick={copy}
                      leftSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                      disabled={!runMeta.final_output}
                    >
                      {copied ? "Copied" : "Copy"}
                    </Button>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>

            <Paper withBorder radius="md" p="sm">
              <ScrollArea h={220} offsetScrollbars type="auto">
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {runMeta.final_output ?? ""}
                </Text>
              </ScrollArea>
            </Paper>
          </Box>

          {/* Tools */}
          <Box>
            <Text size="sm" fw={600} mb={6}>
              Tool calls ({tools.length})
            </Text>

            {tools.length === 0 ? (
              <Text size="sm" c="dimmed">
                No tools were called.
              </Text>
            ) : (
              <Accordion variant="separated" radius="md">
                {tools.map((t, idx) => {
                  const pretty = safePrettyJson(t.args);
                  const ts = formatTimestamp(t.created_at);

                  return (
                    <Accordion.Item key={`${t.tool}-${idx}`} value={`${idx}`}>
                      <Accordion.Control>
                        <Group justify="space-between" w="100%" wrap="nowrap">
                          <Text size="sm" fw={600}>
                            {idx + 1}. {t.tool}
                          </Text>
                          {ts ? (
                            <Text size="xs" c="dimmed">
                              {ts}
                            </Text>
                          ) : null}
                        </Group>
                      </Accordion.Control>

                      <Accordion.Panel>
                        {!pretty.ok ? (
                          <Alert color="yellow" title="Arguments are not valid JSON" mb="xs">
                            Showing raw text.
                          </Alert>
                        ) : null}

                        <Paper withBorder radius="md" p="sm">
                          <ScrollArea h={180} offsetScrollbars type="auto">
                            <Text
                              size="sm"
                              style={{
                                whiteSpace: "pre",
                                fontFamily: "var(--mantine-font-family-monospace)",
                              }}
                            >
                              {pretty.text}
                            </Text>
                          </ScrollArea>
                        </Paper>
                      </Accordion.Panel>
                    </Accordion.Item>
                  );
                })}
              </Accordion>
            )}
          </Box>
        </Stack>
      )}
    </Modal>
  );
}
