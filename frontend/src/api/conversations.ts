import api from "./client";
import { endpoints } from "./endpoints";
import type { TokenUsageSummary } from "../auth/AuthContext";

export type ConversationListItem = {
  id: number;
  kind: "default" | "approvals";
  title: string;
  created_at: string;
  updated_at: string;
  run_count: number;
  token_usage: TokenUsageSummary;
};

export type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type ConversationDetail = {
  id: number;
  kind: "default" | "approvals";
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
};

export type ConversationCreateResponse = {
  id: number;
  kind: "default" | "approvals";
  title: string;
  created_at: string;
  updated_at: string;
};

export async function fetchConversations() {
  const res = await api.get<ConversationListItem[]>(endpoints.agent.conversations);
  return res.data;
}

export async function fetchConversationById(conversationId: number) {
  const res = await api.get<ConversationDetail>(endpoints.agent.conversationById(conversationId));
  return res.data;
}

export async function createConversation(kind: "default" | "approvals" = "default") {
  const res = await api.post<ConversationCreateResponse>(
    endpoints.agent.conversations,
    undefined,
    { params: { kind } },
  );
  return res.data;
}

export async function openApprovalsConversation() {
  const res = await api.get<ConversationCreateResponse>(endpoints.agent.approvalsConversation);
  return res.data;
}

export async function deleteConversation(conversationId: number) {
  const res = await api.delete<{ ok: boolean }>(endpoints.agent.conversationById(conversationId));
  return res.data;
}
