import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Group, Paper, ScrollArea, Switch, Text } from "@mantine/core";
import type { AdminRun } from "../../types/runs";
import { fetchAdminRuns } from "../../api/runs";
import { endpoints } from "../../api/endpoints";
import ClickableTable, { type Column } from "../ClickableTable";
import RunDetailsModal from "../modals/TracesModal";
import { fullHeightPaperStyle } from "../../layout/pageStyles";
import { useAuth } from "../../auth/useAuth";
import { formatTimestampInTimezone } from "../../utils/timezone";

type ErrorShape = {
  response?: {
    data?: {
      detail?: string | {
        explanation?: string;
      };
    };
  };
};

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as ErrorShape)?.response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object" && typeof detail.explanation === "string") {
    return detail.explanation;
  }
  return fallback;
}

function runTypeLabel(run: AdminRun): string {
  return run.run_type === "api_action" ? "API action" : "Agent";
}

function specialistLabel(run: AdminRun): string {
  if (run.run_type === "api_action") return "—";
  return run.specialist_key || "general";
}

function runSummary(run: AdminRun): string {
  if (run.run_type === "api_action") {
    return run.action_name || run.prompt.replace(/^\[api\]\s*/i, "") || "(API action)";
  }
  return run.prompt;
}

export default function AdminTracesPage() {
  const { timezone } = useAuth();
  const [runs, setRuns] = useState<AdminRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showApiActions, setShowApiActions] = useState(false);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const buildRunUrl = useCallback((id: number) => endpoints.admin.agentRunById(id), []);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchAdminRuns();
        if (!cancelled) {
          setRuns(data);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(getErrorMessage(err, "Not authorized"));
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

  const columns = useMemo<Column<AdminRun>[]>(() => {
    return [
      { header: "ID", cell: (r) => r.id },
      { header: "User", cell: (r) => r.user_id },
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
        style: { maxWidth: 760, whiteSpace: "pre-wrap" },
      },
    ];
  }, [timezone]);

  const visibleRuns = useMemo(() => {
    if (showApiActions) return runs;
    return runs.filter((run) => run.run_type !== "api_action");
  }, [runs, showApiActions]);

  return (
    <>
      <Paper radius="md" p="sm" style={fullHeightPaperStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingLeft: 12, paddingRight: 12, marginBottom: 8 }}>
          <Text fw={600} size="xl">Admin runs</Text>
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
          <ScrollArea h={480} type="auto" offsetScrollbars>
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
        title="Admin run details"
      />
    </>
  );
}
