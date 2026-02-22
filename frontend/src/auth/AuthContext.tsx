import { createContext } from "react";

export type PermissionDetail = {
  permission: string;
  tool: string;
  tool_label: string;
  category: string;
  category_label: string;
  title: string;
  description: string;
};

export type TokenUsageSummary = {
  llm_input_tokens: number;
  llm_output_tokens: number;
  llm_total_tokens: number;
  stt_input_tokens: number;
  stt_output_tokens: number;
  stt_total_tokens: number;
  all_input_tokens: number;
  all_output_tokens: number;
  all_total_tokens: number;
};

export type Me = {
  id: number;
  email: string;
  roles: string[];
  permissions: string[];
  permission_details: PermissionDetail[];
  timezone: string;
  token_usage: TokenUsageSummary;
};

export type UserNotification = {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
};

export type AuthContextType = {
  token: string | null;
  isReady: boolean;

  me: Me | null;
  meLoading: boolean;
  meError: string | null;
  timezone: string;
  refreshMe: () => Promise<void>;
  setTimezone: (timezone: string) => Promise<void>;

  notifications: UserNotification[];
  unreadCount: number;
  markNotificationRead: (id: number) => Promise<void>;

  login: (token: string) => void;
  logout: () => void;
};

export const AuthContext = createContext<AuthContextType | null>(null);
