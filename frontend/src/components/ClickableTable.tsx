import type { ReactNode } from "react";
import { Table } from "@mantine/core";

export type Column<T> = {
  header: ReactNode;
  cell: (row: T) => ReactNode;
  style?: React.CSSProperties;
};

type Props<T> = {
  rows: T[];
  columns: Column<T>[];
  onRowClick?: (row: T) => void;
  getRowKey: (row: T) => string | number;
};

export default function ClickableTable<T>({
  rows,
  columns,
  onRowClick,
  getRowKey,
}: Props<T>) {
  return (
    <Table striped highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          {columns.map((c, idx) => (
            <Table.Th key={idx}>{c.header}</Table.Th>
          ))}
        </Table.Tr>
      </Table.Thead>

      <Table.Tbody>
        {rows.map((row) => (
          <Table.Tr
            key={getRowKey(row)}
            style={onRowClick ? { cursor: "pointer" } : undefined}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
          >
            {columns.map((c, idx) => (
              <Table.Td key={idx} style={c.style}>
                {c.cell(row)}
              </Table.Td>
            ))}
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
