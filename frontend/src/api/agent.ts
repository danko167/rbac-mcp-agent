import api from "./client";
import { endpoints } from "./endpoints";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AgentRunResponse = {
  result?: string;
  conversation_id?: number;
};

export type AgentTranscriptionResponse = {
  text: string;
  conversation_id?: number;
};

export async function runAgent(
  prompt: string,
  messages: ChatMessage[],
  conversationId?: number | null,
  options?: { suppressUserMessage?: boolean },
) {
  const res = await api.post<AgentRunResponse>(
    endpoints.agent.run,
    {
      prompt,
      messages,
      conversation_id: conversationId ?? undefined,
      suppress_user_message: options?.suppressUserMessage ?? false,
    }
  );
  return res.data;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Failed to read audio blob"));
        return;
      }
      const base64 = result.split(",")[1] ?? "";
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read audio blob"));
    reader.readAsDataURL(blob);
  });
}

export async function transcribeAudio(blob: Blob, conversationId?: number | null) {
  const audioBase64 = await blobToBase64(blob);
  const res = await api.post<AgentTranscriptionResponse>(endpoints.agent.transcribe, {
    audio_base64: audioBase64,
    mime_type: blob.type || "audio/webm",
    file_name: "speech.webm",
    language: "en",
    conversation_id: conversationId ?? undefined,
  });
  return res.data;
}
