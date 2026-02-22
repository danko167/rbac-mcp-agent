import { useEffect, useMemo, useState, useRef } from "react";
import { useSearchParams } from "react-router";
import { Badge, Box, Button, Divider, Group, Kbd, Paper, ScrollArea, Stack, Switch, Text, Textarea, Title, Tooltip } from "@mantine/core";
import { IconLock, IconMessagePlus, IconMicrophone, IconRobot } from "@tabler/icons-react";
import type { AxiosError } from "axios";
import { runAgent, type ChatMessage } from "../api/agent";
import { createConversation, fetchConversationById } from "../api/conversations";
import { useLayoutSlots } from "../layout/useLayoutSlots";
import classes from "../assets/styles/AgentPage.module.css";
import { useAuth } from "../auth/useAuth";
import { displayNameFromEmail } from "../utils/displayName";
import PermissionsModal from "../components/modals/PermissionsModal";
import { buildNoticeAssistantMessage, buildNoticePrompt } from "./agent/notice";
import { useHoldToTalk } from "./agent/useHoldToTalk";

type ErrorResponse = {
  detail?: string | {
    code?: string;
    explanation?: string;
    next_actions?: string[];
  };
};

export default function AgentPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { setLeft, clearLeft } = useLayoutSlots();
  const { me, notifications } = useAuth();
  const userName = useMemo(() => displayNameFromEmail(me?.email), [me?.email]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [autoRunAfterTranscribe, setAutoRunAfterTranscribe] = useState(false);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [permsOpen, setPermsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const activeConversationId = useMemo(() => {
    const raw = searchParams.get("conversation");
    if (!raw) return null;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed <= 0) return null;
    return parsed;
  }, [searchParams]);
  const notice = searchParams.get("notice");

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const handledNoticeRef = useRef<Set<string>>(new Set());
  const isInteractionBusy =
    conversationLoading
    || loading
    || transcribing
    || recording
    || !!prompt.trim();

  useEffect(() => {
    // scroll to the sentinel at the bottom
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  useEffect(() => {
    if (!activeConversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;

    void (async () => {
      setConversationLoading(true);
      setError(null);
      try {
        const data = await fetchConversationById(activeConversationId);
        if (cancelled) return;
        setMessages(
          data.messages
            .filter((message) => message.role === "user" || message.role === "assistant")
            .map((message) => ({ role: message.role, content: message.content }))
        );
      } catch {
        if (!cancelled) {
          setError("Could not load conversation");
          setMessages([]);
        }
      } finally {
        if (!cancelled) {
          setConversationLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeConversationId]);

  useEffect(() => {
    const busyValue = isInteractionBusy ? "1" : "0";
    sessionStorage.setItem("agent:interaction_busy", busyValue);
    window.dispatchEvent(new CustomEvent("agent:interaction_busy_changed", { detail: { busy: isInteractionBusy } }));

    return () => {
      sessionStorage.setItem("agent:interaction_busy", "0");
      window.dispatchEvent(new CustomEvent("agent:interaction_busy_changed", { detail: { busy: false } }));
    };
  }, [isInteractionBusy]);

  useEffect(() => {
    // Keep notice -> assistant message injection single-path here to avoid duplicate chat prompts.
    if (!notice || !activeConversationId) {
      return;
    }
    if (conversationLoading || loading || transcribing || recording) {
      return;
    }
    if (handledNoticeRef.current.has(notice)) {
      return;
    }

    const nextAssistantMessage = buildNoticeAssistantMessage(notice, notifications, me?.id);
    const nextPrompt = buildNoticePrompt(notice);
    handledNoticeRef.current.add(notice);

    const nextSearch = new URLSearchParams(window.location.search);
    nextSearch.delete("notice");
    nextSearch.set("conversation", String(activeConversationId));

    if (nextAssistantMessage) {
      setMessages((prev) => {
        if (prev.some((item) => item.role === "assistant" && item.content === nextAssistantMessage)) {
          return prev;
        }
        return [...prev, { role: "assistant", content: nextAssistantMessage }];
      });

      setSearchParams(nextSearch, { replace: true });
      return;
    }

    if (!nextPrompt) {
      setSearchParams(nextSearch, { replace: true });
      return;
    }

    void (async () => {
      await run(nextPrompt);
      setSearchParams(nextSearch, { replace: true });
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notice, activeConversationId, conversationLoading, loading, transcribing, recording, notifications]);


  const lastAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i].content;
    }
    return "";
  }, [messages]);

  const run = async (promptOverride?: string, options?: { suppressUserMessage?: boolean }) => {
    if (loading || transcribing || recording) return;

    const trimmed = (promptOverride ?? prompt).trim();
    if (!trimmed) return;

    setError(null);
    setLoading(true);

    // optimistic user message uses trimmed text
    const suppressUserMessage = options?.suppressUserMessage ?? false;
    const userMsg: ChatMessage = { role: "user", content: trimmed };
    const nextMessages = suppressUserMessage ? messages : [...messages, userMsg];
    if (!suppressUserMessage) {
      setMessages(nextMessages);
    }

    // clear the input immediately (feels snappy)
    setPrompt("");

    try {
      const data = await runAgent(trimmed, nextMessages, activeConversationId, {
        suppressUserMessage,
      });
      const assistantText = data?.result ?? "";

      if (data?.conversation_id && data.conversation_id !== activeConversationId) {
        const next = new URLSearchParams(searchParams);
        next.set("conversation", String(data.conversation_id));
        setSearchParams(next, { replace: true });
      }

      setMessages((prev) => [...prev, { role: "assistant", content: assistantText }]);
    } catch (err: unknown) {
      // restore the input if it failed (optional but nice)
      if (!suppressUserMessage) {
        setPrompt(trimmed);
      }

      // Remove the optimistically-added user message if request fails
      if (!suppressUserMessage) {
        setMessages((prev) => prev.slice(0, -1));
      }

      if (err instanceof Error) {
        const axiosErr = err as AxiosError<ErrorResponse>;
        const detail = axiosErr.response?.data?.detail;
        if (typeof detail === "string") {
          setError(detail);
        } else if (detail && typeof detail === "object") {
          const explanation = detail.explanation ?? "Not authorized";
          const next = Array.isArray(detail.next_actions) ? detail.next_actions : [];
          const nextText = next.length ? ` Next: ${next.join(" ")}` : "";
          setError(`${explanation}${nextText}`);
        } else {
          setError(axiosErr.message ?? "Agent failed");
        }
      } else {
        setError("Agent failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const startConversation = async () => {
    if (loading || transcribing || recording || conversationLoading) return;

    setError(null);
    setConversationLoading(true);
    try {
      const created = await createConversation();
      const next = new URLSearchParams(searchParams);
      next.set("conversation", String(created.id));
      setSearchParams(next, { replace: true });
    } catch {
      setError("Could not start a new conversation");
    } finally {
      setConversationLoading(false);
    }
  };

  const {
    startHoldToTalk,
    stopHoldToTalk,
    cleanupRecorder,
  } = useHoldToTalk({
    disabled: loading || conversationLoading,
    activeConversationId,
    recording,
    transcribing,
    setRecording,
    setTranscribing,
    prompt,
    autoRunAfterTranscribe,
    onPromptChange: setPrompt,
    onRun: run,
    onConversationIdChange: (conversationId) => {
      const next = new URLSearchParams(searchParams);
      next.set("conversation", String(conversationId));
      setSearchParams(next, { replace: true });
    },
    onError: (message) => setError(message || null),
  });

  const holdKeyPressedRef = useRef(false);

  const isTypingTarget = (target: EventTarget | null) => {
    if (!(target instanceof HTMLElement)) return false;
    const tag = target.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
  };

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // Shift + Space
      if (e.code !== "Space" || !e.shiftKey) return;

      // don't hijack while typing in inputs/textareas/contenteditable
      if (isTypingTarget(e.target)) return;

      // avoid auto-repeat while holding
      if (e.repeat) return;

      if (holdKeyPressedRef.current) return;

      if (loading || transcribing || recording || conversationLoading) return;

      e.preventDefault();
      holdKeyPressedRef.current = true;
      void startHoldToTalk();
    };

    const onKeyUp = (e: KeyboardEvent) => {
      // stop on Space release (even if Shift already released)
      if (e.code !== "Space") return;

      if (!holdKeyPressedRef.current) return;

      e.preventDefault();
      holdKeyPressedRef.current = false;
      stopHoldToTalk();
    };

    const onBlur = () => {
      if (!holdKeyPressedRef.current) return;
      holdKeyPressedRef.current = false;
      stopHoldToTalk();
    };

    window.addEventListener("keydown", onKeyDown, { passive: false });
    window.addEventListener("keyup", onKeyUp, { passive: false });
    window.addEventListener("blur", onBlur);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
    };
  }, [loading, transcribing, recording, conversationLoading, startHoldToTalk, stopHoldToTalk]);

  // Inject left panel content into layout
  useEffect(() => {
    setLeft(
      <Paper withBorder radius="md" p="sm" className={classes.leftCard}>
        <Stack gap="sm">
          <Group justify="space-between" align="center" wrap="nowrap">
            <Group>
              <Text size="xs" c="dimmed">Current role</Text>
              {(me?.roles ?? []).map((role) => (
                <Badge key={role} variant="light" color={role === "admin" ? "red" : role === "pro" ? "violet" : "orange"}>
                  {role}
                </Badge>
              ))}
            </Group>

            <Button
              variant="subtle"
              size="xs"
              color="teal"
              radius="md"
              leftSection={<IconLock size={16} />}
              onClick={() => setPermsOpen(true)}
              px={6}
            >
              Permissions
            </Button>
          </Group>

          <Divider />

          <Stack gap="xs">
            <Textarea
              label={
                <Group w="100%" justify="space-between" align="center" wrap="nowrap">
                  <Box>
                    <Text size="sm" fw={500}>Agent prompt</Text>
                    <Text size="xs" c="dimmed">Tell the agent what to do.</Text>
                  </Box>

                  <Button
                    variant="light"
                    radius="md"
                    color="teal"
                    size="xs"
                    onClick={() => { void startConversation(); }}
                    leftSection={<IconMessagePlus size={16} />}
                    disabled={loading || transcribing || recording || conversationLoading}
                  >
                    New conversation
                  </Button>
                </Group>
              }
              labelProps={{
                style: {
                  width: "100%",
                  display: "block", // important: label defaults can behave shrink-to-fit
                },
              }}
              // remove description since you’re rendering it inside label now
              placeholder="What can you do?"
              radius="md"
              autosize
              minRows={4}
              maxRows={8}
              value={prompt}
              onChange={(e) => setPrompt(e.currentTarget.value)}
              disabled={loading || conversationLoading}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!loading && !transcribing && !recording && !conversationLoading) run();
                }
              }}
            />
            <Text size="xs" c="dimmed">
              <Kbd size="xs">Shift</Kbd> + <Kbd size="xs">Enter</Kbd> for newline
            </Text>


            <Button onClick={() => { void run(); }} radius="md" color="teal" disabled={loading || transcribing || recording || conversationLoading || !prompt.trim()} loading={loading} leftSection={<IconRobot size={18} />}>
              Run agent
            </Button>

          </Stack>

          <Divider />

          <Stack className={classes.speechRow} gap="xs">
            <Button
              variant={recording ? "filled" : "light"}
              radius="md"
              color="grape"
              leftSection={<IconMicrophone size={18} />}
              disabled={loading || transcribing || conversationLoading}
              onPointerDown={(e) => {
                e.preventDefault();
                void startHoldToTalk();
              }}
              onPointerUp={stopHoldToTalk}
              onPointerCancel={stopHoldToTalk}
              onPointerLeave={stopHoldToTalk}
            >
              {recording ? "Release to transcribe" : transcribing ? "Transcribing..." : "Hold to talk"}
            </Button>

            <Text size="xs" c="dimmed" mb="md">
              <Kbd size="xs">Shift</Kbd> + <Kbd size="xs">Space</Kbd> to hold and talk (try it out!)
            </Text>

            <Tooltip
              withArrow
              multiline
              w={300}
              label="When enabled, the app sends transcribed speech to the agent immediately after you release the Hold to talk button. When disabled, transcribed text is added to the prompt and you run it manually with the Run agent button."
            >
              <Switch
                size="sm"
                radius="xl"
                label="Auto-run after transcription"
                checked={autoRunAfterTranscribe}
                onChange={(event) => setAutoRunAfterTranscribe(event.currentTarget.checked)}
                disabled={loading || transcribing || recording || conversationLoading}
              />
            </Tooltip>

            <Group gap="xs" align="center">
              <Text size="xs" c="dimmed">Speech mode:</Text>
              <Badge size="sm" variant="light" color={autoRunAfterTranscribe ? "teal" : "gray"}>
                {autoRunAfterTranscribe ? "Auto-send" : "Manual send"}
              </Badge>
            </Group>

            <Text size="xs" c="dimmed">
              Press and hold to record in English. Release to convert speech to text.
            </Text>
          </Stack>

          {error && (
            <Text c="red" size="sm" className={classes.error}>
              {error}
            </Text>
          )}
        </Stack>
      </Paper>
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    prompt,
    loading,
    transcribing,
    recording,
    autoRunAfterTranscribe,
    error,
    conversationLoading,
    lastAssistant,
    me,
    setLeft,
  ]);

  // Unmount cleanup ONLY
  useEffect(() => {
    return () => {
      clearLeft();
      cleanupRecorder();
    };
  }, [clearLeft, cleanupRecorder]);

  // RIGHT content only
  return (
    <>
      <Paper withBorder radius="md" p="sm" style={{ display: "flex", flexDirection: "column", minHeight: 0, height: "100%" }}>
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

        {conversationLoading ? (
          <Box className={classes.emptyState}>
            <Text fw={600}>Loading conversation...</Text>
          </Box>
        ) : messages.length === 0 ? (
          <Box className={classes.emptyState}>
            <Text fw={600}>No answers yet</Text>
            <Text size="sm" c="dimmed" mt={4}>
              Run the agent from the left panel to see responses here.
            </Text>
          </Box>
        ) : (
          <ScrollArea h={570} type="auto" offsetScrollbars>
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

      <PermissionsModal
        opened={permsOpen}
        onClose={() => setPermsOpen(false)}
        permissionDetails={me?.permission_details ?? []}
      />
    </>

  );
}
