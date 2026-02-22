import { useCallback, useRef } from "react";
import { transcribeAudio } from "../../api/agent";

type Params = {
  disabled: boolean;
  activeConversationId: number | null;
  recording: boolean;
  transcribing: boolean;
  setRecording: (next: boolean) => void;
  setTranscribing: (next: boolean) => void;
  prompt: string;
  autoRunAfterTranscribe: boolean;
  onPromptChange: (nextPrompt: string) => void;
  onRun: (promptOverride?: string) => Promise<void>;
  onConversationIdChange: (conversationId: number) => void;
  onError: (message: string) => void;
};

export function useHoldToTalk({
  disabled,
  activeConversationId,
  recording,
  transcribing,
  setRecording,
  setTranscribing,
  prompt,
  autoRunAfterTranscribe,
  onPromptChange,
  onRun,
  onConversationIdChange,
  onError,
}: Params) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef<number>(0);

  const stopStream = useCallback(() => {
    if (!streamRef.current) return;
    streamRef.current.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const cleanupRecorder = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    mediaRecorderRef.current = null;
    setRecording(false);
    stopStream();
  }, [setRecording, stopStream]);

  const startHoldToTalk = useCallback(async () => {
    if (disabled || transcribing || recording) return;
    onError("");

    if (typeof window === "undefined" || !("MediaRecorder" in window) || !navigator.mediaDevices?.getUserMedia) {
      onError("This browser does not support microphone recording.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      audioChunksRef.current = [];

      const preferredMimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";

      const recorder = preferredMimeType
        ? new MediaRecorder(stream, { mimeType: preferredMimeType })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        const durationMs = Date.now() - recordingStartedAtRef.current;
        const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;
        stopStream();

        if (durationMs < 250 || audioBlob.size < 1_024) return;

        setTranscribing(true);
        try {
          const data = await transcribeAudio(audioBlob, activeConversationId);
          if (data.conversation_id && data.conversation_id !== activeConversationId) {
            onConversationIdChange(data.conversation_id);
          }
          const text = (data.text ?? "").trim();
          if (text) {
            const combinedPrompt = `${prompt.trimEnd()} ${text}`.trim();
            onPromptChange(combinedPrompt);
            if (autoRunAfterTranscribe) {
              await onRun(combinedPrompt);
            }
          }
        } catch (err: unknown) {
          if (err instanceof Error) onError(err.message);
          else onError("Transcription failed");
        } finally {
          setTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recordingStartedAtRef.current = Date.now();
      recorder.start();
      setRecording(true);
    } catch {
      stopStream();
      setRecording(false);
      onError("Microphone access was denied or failed.");
    }
  }, [
    disabled,
    transcribing,
    recording,
    onError,
    stopStream,
    setTranscribing,
    activeConversationId,
    onConversationIdChange,
    prompt,
    onPromptChange,
    autoRunAfterTranscribe,
    onRun,
    setRecording,
  ]);

  const stopHoldToTalk = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (!recorder) {
      setRecording(false);
      stopStream();
      return;
    }

    if (recorder.state !== "inactive") recorder.stop();
    setRecording(false);
  }, [setRecording, stopStream]);

  return {
    startHoldToTalk,
    stopHoldToTalk,
    cleanupRecorder,
  };
}
