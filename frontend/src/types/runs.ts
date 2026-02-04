export type RunBase = {
  id: number;
  prompt: string;
};

export type UserRun = RunBase & {
  final_output: string | null;
};

export type AdminRun = RunBase & {
  user_id: number;
};
