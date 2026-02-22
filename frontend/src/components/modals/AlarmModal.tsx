import { Button, Group, Modal, Stack, Text } from "@mantine/core";
import type { UserNotification } from "../../auth/AuthContext";
import { formatTimestampInTimezone } from "../../utils/timezone";

type Props = {
  opened: boolean;
  onClose: () => void;
  activeAlarm: UserNotification | null;
  timezone: string;
  audioError: string | null;
  alarmSoundReady: boolean;
  onPlay: () => Promise<void>;
  onStop: () => void;
  onMarkRead: (id: number) => Promise<void>;
};

export default function AlarmModal({
  opened,
  onClose,
  activeAlarm,
  timezone,
  audioError,
  alarmSoundReady,
  onPlay,
  onStop,
  onMarkRead,
}: Props) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Text fw={600}>Alarm fired</Text>}
      radius="md"
      centered
    >
      <Stack gap="sm">
        <Text size="sm" fw={600}>
          {activeAlarm?.payload?.title && typeof activeAlarm.payload.title === "string"
            ? activeAlarm.payload.title
            : "An alarm is due."}
        </Text>
        <Text size="xs" c="dimmed">
          {activeAlarm
            ? formatTimestampInTimezone(activeAlarm.created_at, timezone)
            : ""}
        </Text>
        {audioError ? (
          <Text size="xs" c="red">{audioError}</Text>
        ) : null}
        <Group>
          <Button
            size="xs"
            radius="md"
            color="teal"
            onClick={() => void onPlay()}
          >
            {alarmSoundReady ? "Play" : "Enable sound"}
          </Button>
          <Button
            size="xs"
            radius="md"
            color="red"
            onClick={onStop}
          >
            Stop
          </Button>
          {activeAlarm ? (
            <Button
              size="xs"
              radius="md"
              variant="light"
              onClick={() => {
                void onMarkRead(activeAlarm.id);
                onStop();
                onClose();
              }}
            >
              Mark read
            </Button>
          ) : null}
        </Group>
      </Stack>
    </Modal>
  );
}
