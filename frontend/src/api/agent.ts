import api from "./client";
import { endpoints } from "./endpoints";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AgentRunResponse = {
  result?: string;
};

export async function runAgent(prompt: string, messages: ChatMessage[]) {
  const res = await api.post<AgentRunResponse>(
    endpoints.agent.run,
    { messages },
    { params: { prompt } }
  );
  return res.data;
}
