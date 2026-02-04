import { useEffect, useMemo, useState, useRef } from "react";
import { Box, Button, Group, Kbd, Paper, ScrollArea, Stack, Text, Textarea, Title } from "@mantine/core";
import { IconRestore, IconRobot } from "@tabler/icons-react";
import type { AxiosError } from "axios";
import { runAgent, type ChatMessage } from "../api/agent";
import { useLayoutSlots } from "../layout/useLayoutSlots";
import classes from "../assets/styles/AgentPage.module.css";
import { useAuth } from "../auth/useAuth";
import { displayNameFromEmail } from "../utils/displayName";

type ErrorResponse = {
  detail?: string;
};

export default function AgentPage() {
  const { setLeft, clearLeft } = useLayoutSlots();
  const { me } = useAuth();
  const userName = useMemo(() => displayNameFromEmail(me?.email), [me?.email]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // scroll to the sentinel at the bottom
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);


  const lastAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i].content;
    }
    return "";
  }, [messages]);

  const run = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;

    setError(null);
    setLoading(true);

    // optimistic user message uses trimmed text
    const userMsg: ChatMessage = { role: "user", content: trimmed };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);

    // clear the input immediately (feels snappy)
    setPrompt("");

    try {
      const data = await runAgent(trimmed, nextMessages);
      const assistantText = data?.result ?? "";

      setMessages((prev) => [...prev, { role: "assistant", content: assistantText }]);
    } catch (err: unknown) {
      // restore the input if it failed (optional but nice)
      setPrompt(trimmed);

      // Remove the optimistically-added user message if request fails
      setMessages((prev) => prev.slice(0, -1));

      if (err instanceof Error) {
        const axiosErr = err as AxiosError<ErrorResponse>;
        setError(axiosErr.response?.data?.detail ?? axiosErr.message ?? "Agent failed");
      } else {
        setError("Agent failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const resetConversation = () => {
    setMessages([]);
    setError(null);
  };

  // Inject left panel content into layout
  useEffect(() => {
    setLeft(
      <Paper withBorder radius="md" p="sm" className={classes.leftCard}>
        <Stack gap="sm">
          <Textarea
            label="Agent prompt"
            description="Tell the agent what to do."
            placeholder="What can you do?"
            radius="md"
            autosize
            minRows={4}
            maxRows={8}
            value={prompt}
            onChange={(e) => setPrompt(e.currentTarget.value)}
            disabled={loading}
            onKeyDown={(e) => {
              // Enter sends, Shift+Enter makes a newline
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!loading) run();
              }
            }}
          />

          <Text size="xs" c="dimmed">
            <Kbd size="xs">Shift</Kbd> + <Kbd size="xs">Enter</Kbd> for newline
          </Text>

          <Group justify="space-between" align="center">
            <Button onClick={run} fullWidth radius="md" color="teal" disabled={loading || !prompt.trim()} loading={loading} leftSection={<IconRobot size={18} />}>
              Run agent
            </Button>

            {error && (
              <Text c="red" size="sm" className={classes.error}>
                {error}
              </Text>
            )}
          </Group>

          <Button variant="light" radius="md" color="teal" onClick={resetConversation} leftSection={<IconRestore size={18} />}>
            Clear chat
          </Button>
        </Stack>
      </Paper>
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prompt, loading, error, lastAssistant, setLeft]);

  // Unmount cleanup ONLY
  useEffect(() => {
    return () => clearLeft();
  }, [clearLeft]);

  // RIGHT content only
  return (
    <Paper withBorder radius="md" p="sm" className={classes.rightCard}>
      <Group justify="space-between" align="center" mb="sm">
        <Title order={3}>
          <Group gap="xs" align="center">
            <IconRobot size={26} style={{ color: "var(--mantine-color-teal-6)" }} />
            <span>{userName}&apos;s agent</span>
          </Group>
        </Title>

        <Text size="sm" c="dimmed">
          {messages.length} messages
        </Text>
      </Group>

      {messages.length === 0 ? (
        <Box className={classes.emptyState}>
          <Text fw={600}>No answers yet</Text>
          <Text size="sm" c="dimmed" mt={4}>
            Run the agent from the left panel to see responses here.
          </Text>
        </Box>
      ) : (
        <ScrollArea className={classes.chatScroll} type="auto" offsetScrollbars>
          <Stack gap="xs" p="xs">
            {messages.map((m, idx) => (
              <Group
                key={idx}
                justify={m.role === "user" ? "flex-end" : "flex-start"}
                align="flex-start"
              >
                <Box className={m.role === "user" ? classes.userBubble : classes.answerBubble}>
                  <Text size="xs" c={m.role === "user" ? "white" : "dimmed"} mb={4}>
                    {m.role === "user" ? "You" : "Agent"}
                  </Text>
                  <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                    {m.content}
                  </Text>
                </Box>

              </Group>
            ))}
            <div ref={bottomRef} />
          </Stack>
        </ScrollArea>
      )}
    </Paper>

  );
}
