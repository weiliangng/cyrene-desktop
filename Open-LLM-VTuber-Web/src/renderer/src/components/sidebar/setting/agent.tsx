import { Stack, Text } from '@chakra-ui/react';
import { settingStyles } from './setting-styles';

interface AgentProps {
  onSave?: (callback: () => void) => () => void;
  onCancel?: (callback: () => void) => () => void;
}
function Agent(_props: AgentProps): JSX.Element {
  return (
    <Stack {...settingStyles.common.container}>
      <Text fontWeight="bold">OpenClaw</Text>
      <Text>OpenClaw manages conversations, tools, memory and scheduled activity.</Text>
      <Text>Cyrene displays replies and task progress. Hover or activity wakes her; she sleeps after inactivity.</Text>
      <Text>Drop files or use the paperclip to add their paths to your draft. Shift+Enter adds a new line.</Text>
    </Stack>
  );
}
export default Agent;
