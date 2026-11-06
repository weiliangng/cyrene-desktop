import { cancelExternalSpeech } from '@/pet/use-cyrene-control';
import { useChatRun } from '@/pet/chat-run';
import { useAiState } from '@/context/ai-state-context';
import { useWebSocket } from '@/context/websocket-context';
import { useChatHistory } from '@/context/chat-history-context';
import { audioTaskQueue } from '@/utils/task-queue';
import { useSubtitle } from '@/context/subtitle-context';
import { useAudioTask } from './use-audio-task';

export const useInterrupt = () => {
  const { setAiState } = useAiState();
  const { sendMessage } = useWebSocket();
  const { fullResponse, clearResponse } = useChatHistory();
  // const { currentModel } = useLive2DModel();
  const { subtitleText, setSubtitleText } = useSubtitle();
  const { stopCurrentAudioAndLipSync } = useAudioTask();

  const interrupt = (sendSignal = true) => {
    // Stop remains effective after an earlier click, while awaiting acknowledgement,
    // or when a lifecycle task is still visible after local chat state changed.
    if (sendSignal) useChatRun.getState().stop();
    console.log('Interrupting conversation chain');

    stopCurrentAudioAndLipSync();
    cancelExternalSpeech();

    audioTaskQueue.clearQueue();

    setAiState('interrupted');

    if (sendSignal) {
      sendMessage({
        type: 'interrupt-signal',
        text: fullResponse,
      });
    }

    clearResponse();

    if (subtitleText === 'Thinking...') {
      setSubtitleText('');
    }
    console.log('Interrupted!');
  };

  return { interrupt };
};
