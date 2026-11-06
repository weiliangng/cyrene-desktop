import { useEffect, useRef } from 'react';
import { useAiState } from '@/context/ai-state-context';
import { ModelInfo } from '@/context/live2d-config-context';
import { usePetActivity } from './use-pet-activity';
import { externalState } from './external-control';
import { useChatRun } from './chat-run';

export function useCyreneIdle(modelInfo?: ModelInfo) {
  const { aiState } = useAiState();
  const { phase } = useChatRun();
  const { sleeping, setActivity, tick } = usePetActivity();
  const previous = useRef<{ model: unknown; expression: string }>();
  const isCyrene = modelInfo?.name === 'cyrene';
  const busy = phase !== 'idle' || aiState === 'thinking-speaking' || aiState === 'listening' || aiState === 'waiting';

  useEffect(() => {
    setActivity('conversation', isCyrene && busy);
    return () => setActivity('conversation', false);
  }, [isCyrene, busy, setActivity]);

  useEffect(() => {
    if (!isCyrene) return undefined;
    // Poll until the asynchronous Cubism load completes, and also after model reloads.
    const update = () => {
      tick();
      const adapter = (window as any).getLAppAdapter?.();
      const model = adapter?.getModel();
      if (!model?._model || adapter.getExpressionCount() < 1) return;
      externalState.tick(Date.now());
      const expression = externalState.resolveExpression(usePetActivity.getState().sleeping, Date.now());
      // The app is the final authority: sleep and task transitions override agent emotions.
      if (previous.current?.model !== model || previous.current?.expression !== expression) {
        adapter.setExpression(expression);
        previous.current = { model, expression };
        console.info(`[Cyrene] ${sleeping ? 'sleeping' : 'awake'}`);
      }
    };
    update();
    const timer = window.setInterval(update, 100);
    return () => window.clearInterval(timer);
  }, [isCyrene, sleeping, tick]);

  // Restore the idle expression once a conversation finishes.
  useEffect(() => { if (!busy) previous.current = undefined; }, [busy]);
}
