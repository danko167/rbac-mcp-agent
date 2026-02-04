import api from "./client";
import { endpoints } from "./endpoints";
import type { AdminRun, UserRun } from "../types/runs";

export async function fetchUserRuns() {
  const res = await api.get<UserRun[]>(endpoints.agent.runs);
  return res.data;
}

export async function fetchAdminRuns() {
  const res = await api.get<AdminRun[]>(endpoints.admin.agentRuns);
  return res.data;
}
