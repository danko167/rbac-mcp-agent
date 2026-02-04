import { useEffect, useMemo, useState } from "react";
import { Text } from "@mantine/core";
import type { UserRun } from "../types/runs";
import { fetchUserRuns } from "../api/runs";
import { endpoints } from "../api/endpoints";
import RunDetailsModal from "../components/TracesModal";
import RunsTablePageShell from "../components/RunsTablePageShell";
import ClickableTable, { type Column } from "../components/ClickableTable";

export default function TracesPage() {
  const [runs, setRuns] = useState<UserRun[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  useEffect(() => {
    fetchUserRuns()
      .then(setRuns)
      .finally(() => setLoading(false));
  }, []);

  const columns = useMemo<Column<UserRun>[]>(() => {
    return [
      { header: "ID", cell: (r) => r.id },
      {
        header: "Prompt",
        cell: (r) => r.prompt,
        style: { maxWidth: 400, whiteSpace: "pre-wrap" },
      },
      {
        header: "Output",
        cell: (r) => r.final_output ?? "",
        style: { maxWidth: 600, whiteSpace: "pre-wrap" },
      },
    ];
  }, []);

  return (
    <>
      <RunsTablePageShell title="My runs" count={runs.length}>
        {loading ? (
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
        buildUrl={(id) => endpoints.agent.runById(id)}
        title="Run details"
      />
    </>
  );
}
