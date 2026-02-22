import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Group, Paper, ScrollArea, Switch, Text } from "@mantine/core";
import type { UserRun } from "../types/runs";
import { fetchUserRuns } from "../api/runs";
import { endpoints } from "../api/endpoints";
import ClickableTable, { type Column } from "../components/ClickableTable";
import RunDetailsModal from "../components/modals/TracesModal";
import { fullHeightPaperStyle } from "../layout/pageStyles";
import { useAuth } from "../auth/useAuth";
import { formatTimestampInTimezone } from "../utils/timezone";

function runTypeLabel(run: UserRun): string {
  return run.run_type === "api_action" ? "API action" : "Agent";
}

function specialistLabel(run: UserRun): string {
  if (run.run_type === "api_action") return "—";
  return run.specialist_key || "general";
}

function runSummary(run: UserRun): string {
  if (run.run_type === "api_action") {
    return run.action_name || run.prompt.replace(/^\[api\]\s*/i, "") || "(API action)";
  }
  return run.prompt;
}

export default function TracesPage() {
  const { timezone } = useAuth();
  const [runs, setRuns] = useState<UserRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showApiActions, setShowApiActions] = useState(false);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const buildRunUrl = useCallback((id: number) => endpoints.agent.runById(id), []);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchUserRuns();
        if (!cancelled) {
          setRuns(data);
        }
      } catch {
        if (!cancelled) {
          setError("Failed to load runs");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const columns = useMemo<Column<UserRun>[]>(() => {
    return [
      { header: "ID", cell: (r) => r.id },
      {
        header: "Type",
        cell: (r) => (
          <Badge variant="light" color={r.run_type === "api_action" ? "grape" : "blue"}>
            {runTypeLabel(r)}
          </Badge>
        ),
      },
      {
        header: "Status",
        cell: (r) => (
          <Badge variant="light" color={r.status === "error" ? "red" : "teal"}>
            {String(r.status || "ok").toUpperCase()}
          </Badge>
        ),
      },
      {
        header: "Specialist",
        cell: (r) => specialistLabel(r),
      },
      {
        header: "Created",
        cell: (r) => formatTimestampInTimezone(r.created_at, timezone),
      },
      {
        header: "Summary",
        cell: (r) => runSummary(r),
        style: { maxWidth: 820, whiteSpace: "pre-wrap" },
      },
    ];
  }, [timezone]);

  const visibleRuns = useMemo(() => {
    if (showApiActions) return runs;
    return runs.filter((run) => run.run_type !== "api_action");
  }, [runs, showApiActions]);

  return (
    <>
      <Paper withBorder radius="md" p="sm" style={fullHeightPaperStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingLeft: 12, paddingRight: 12, marginBottom: 8 }}>
          <Text fw={600} size="xl">My runs</Text>
          <Group gap="md">
            <Switch
              size="sm"
              checked={showApiActions}
              onChange={(event) => setShowApiActions(event.currentTarget.checked)}
              label="Show API actions"
            />
            <Text size="sm" c="dimmed">
              {visibleRuns.length} shown
            </Text>
          </Group>
        </div>

        {error ? (
          <Text c="red" style={{ padding: 12 }}>{error}</Text>
        ) : loading ? (
          <Text size="sm" style={{ padding: 12 }}>Loading...</Text>
        ) : (
          <ScrollArea h={570} type="auto" offsetScrollbars>
            <ClickableTable
              rows={visibleRuns}
              columns={columns}
              getRowKey={(run) => run.id}
              onRowClick={(run) => {
                setSelectedRunId(run.id);
                setDetailsOpen(true);
              }}
            />
          </ScrollArea>
        )}
      </Paper>

      <RunDetailsModal
        opened={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        runId={selectedRunId}
        buildUrl={buildRunUrl}
        title="Run details"
      />
    </>
  );
}
