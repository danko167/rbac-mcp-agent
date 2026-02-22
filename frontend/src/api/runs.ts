import { endpoints } from "./endpoints";
import type { AdminRun, UserRun } from "../types/runs";
import { getData } from "./http";

export async function fetchUserRuns() {
  return getData<UserRun[]>(endpoints.agent.runs);
}

export async function fetchAdminRuns() {
  return getData<AdminRun[]>(endpoints.admin.agentRuns);
}
