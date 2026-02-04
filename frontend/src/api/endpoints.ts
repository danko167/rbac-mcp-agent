export const endpoints = {
  auth: {
    login: "/login",
    me: "/me",
  },
  agent: {
    run: "/agent/run",
    runs: "/agent/runs",
    runById: (id: number | string) => `/agent/runs/${id}`,
  },
  admin: {
    agentRuns: "/admin/agent/runs",
    agentRunById: (id: number | string) => `/admin/agent/runs/${id}`,
  },
} as const;
