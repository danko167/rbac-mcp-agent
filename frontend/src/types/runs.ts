export type RunBase = {
  id: number;
  prompt: string;
  run_type: "agent" | "api_action";
  action_name: string | null;
  created_at: string;
  status: string;
  specialist_key: string | null;
  final_output: string | null;
};

export type UserRun = RunBase & {
  conversation_id?: number | null;
};

export type AdminRun = RunBase & {
  user_id: number;
};
