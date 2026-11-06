import { useState } from 'react';
import { useWebSocket } from '@/context/websocket-context';
import { useAiState } from '@/context/ai-state-context';
import { useDraft } from '@/pet/draft';

export function useTextInput() {
  const { text: inputText, setText, addPaths } = useDraft();
  const [isComposing, setIsComposing] = useState(false);
  const wsContext = useWebSocket();
  const { aiState, setAiState } = useAiState();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setText(e.target.value);
  const handleAttachFiles = async () => {
    const paths = await (window.api as any)?.pickFiles?.();
    if (paths?.length) addPaths(paths);
  };
  const handleSend = async () => {
    if (!inputText.trim() || wsContext.wsState !== 'OPEN' || aiState === 'thinking-speaking') return;
    // Forward exactly what the user sees, including whitespace and explicitly added paths.
    wsContext.sendMessage({ type: 'text-input', text: inputText });
    setAiState('thinking-speaking');
    // Keep the draft until the backend acknowledges it; disconnects cannot eat unsent text.
  };
  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (isComposing || e.nativeEvent.isComposing) return;
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void handleSend(); }
  };
  return {
    inputText, setInputText: handleInputChange, handleSend, handleAttachFiles, handleKeyPress,
    handleCompositionStart: () => setIsComposing(true), handleCompositionEnd: () => setIsComposing(false),
  };
}
