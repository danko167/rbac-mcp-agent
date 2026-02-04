import { useEffect, useMemo, useState } from "react";
import { Text } from "@mantine/core";
import type { AdminRun } from "../types/runs";
import { fetchAdminRuns } from "../api/runs";
import { endpoints } from "../api/endpoints";
import RunDetailsModal from "../components/TracesModal";
import RunsTablePageShell from "../components/RunsTablePageShell";
import ClickableTable, { type Column } from "../components/ClickableTable";

export default function AdminTracesPage() {
  const [runs, setRuns] = useState<AdminRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  useEffect(() => {
    fetchAdminRuns()
      .then(setRuns)
      .catch((e) => setError(e?.response?.data?.detail ?? "Not authorized"))
      .finally(() => setLoading(false));
  }, []);

  const columns = useMemo<Column<AdminRun>[]>(() => {
    return [
      { header: "ID", cell: (r) => r.id },
      { header: "User", cell: (r) => r.user_id },
      {
        header: "Prompt",
        cell: (r) => r.prompt,
        style: { maxWidth: 700, whiteSpace: "pre-wrap" },
      },
    ];
  }, []);

  return (
    <>
      <RunsTablePageShell title="Admin runs" count={runs.length}>
        {error ? (
          <Text c="red">{error}</Text>
        ) : loading ? (
          <Text size="sm">Loading...</Text>
        ) : (
          <ClickableTable
            rows={runs}
            columns={columns}
            getRowKey={(r) => r.id}
            onRowClick={(r) => {
              setSelectedRunId(r.id);
              setDetailsOpen(true);
            }}
          />
        )}
      </RunsTablePageShell>

      <RunDetailsModal
        opened={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        runId={selectedRunId}
        buildUrl={(id) => endpoints.admin.agentRunById(id)}
        title="Admin run details"
      />
    </>
  );
}
