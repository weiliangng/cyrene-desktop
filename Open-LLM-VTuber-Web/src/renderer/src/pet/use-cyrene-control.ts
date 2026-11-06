import { useEffect, useRef } from 'react';
import { wsService } from '@/services/websocket-service';
import { useSubtitle } from '@/context/subtitle-context';
import { useAiState } from '@/context/ai-state-context';
import { audioTaskQueue } from '@/utils/task-queue';
import { usePetActivity } from './use-pet-activity';
import { externalState, useExternalControl } from './external-control';
import { isPetLayout } from './layout';

const pendingSpeech = new Map<string, () => void>();
export function cancelExternalSpeech() {
  for (const cancel of [...pendingSpeech.values()]) cancel();
}

export function emitControlEvent(event: string, data: Record<string, unknown> = {}, command_id?: string) {
  if (wsService.getCurrentState() === 'OPEN') wsService.sendMessage({ type: 'cyrene-event', event, data, command_id });
}

export function useCyreneControl(addAudioTask: (options: any) => Promise<void>, stopAudio: () => void) {
  const { setSubtitleText } = useSubtitle();
  const { setAiState } = useAiState();
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const captionVersion = useRef(0);
  const caption = (text: string, duration = 8000, command_id?: string) => {
    emitControlEvent("output.subtitle", { text }, command_id);
    captionVersion.current += 1;
    const version = captionVersion.current;
    clearTimeout(timer.current);
    setSubtitleText(text);
    useExternalControl.getState().captionSet(text);
    externalState.awakeUntil = Math.max(externalState.awakeUntil, Date.now() + duration);
    (window as any).inputSubtitle?.open?.();
    timer.current = setTimeout(() => {
      if (version === captionVersion.current) useExternalControl.getState().captionSet('');
    }, duration);
  };

  useEffect(() => {
    let readyModel: unknown;
    const interval = setInterval(() => {
      const active = externalState.tick(Date.now());
      usePetActivity.getState().setActivity('external', active);
      useExternalControl.getState().refresh();
      const model = (window as any).getLAppAdapter?.()?.getModel();
      if (model?._modelSetting && model._textureCount >= model._modelSetting.getTextureCount() && model !== readyModel) {
        readyModel = model;
        emitControlEvent('client.ready');
        emitControlEvent(usePetActivity.getState().sleeping ? 'pet.sleeping' : 'pet.awake');
        emitControlEvent('layout.changed', { version: 1, matrix: Array.from(model._modelMatrix.getArray()) });
      }
    }, 250);
    const layout = (event: Event) => emitControlEvent('layout.changed', (event as CustomEvent).detail);
    window.addEventListener('cyrene-layout-saved', layout);
    const unsubscribe = usePetActivity.subscribe((state, previous) => {
      if (state.sleeping !== previous.sleeping) emitControlEvent(state.sleeping ? 'pet.sleeping' : 'pet.awake', { expression: externalState.resolveExpression(state.sleeping, Date.now()) });
    });
    return () => {
      clearInterval(interval); clearTimeout(timer.current); unsubscribe();
      window.removeEventListener('cyrene-layout-saved', layout);
    };
  }, []);

  return {
    reset: () => { stopAudio(); cancelExternalSpeech(); externalState.reset(); usePetActivity.getState().setActivity('external', false); useExternalControl.getState().refresh(); },
    snapshot: (state: any) => {
      externalState.reset();
      for (const task of state.tasks || []) externalState.task(task, Date.now(), true);
      if (state.expression?.expires_at * 1000 > Date.now()) {
        externalState.setExpression(state.expression.name, state.expression.expires_at * 1000 - Date.now(), Date.now());
      }
      useExternalControl.getState().refresh();
      // Reconnection needs a new ready acknowledgement even when the model remains loaded.
      const model = (window as any).getLAppAdapter?.()?.getModel();
      if (model?._model && model?._modelSetting && model._textureCount >= model._modelSetting.getTextureCount()) {
        emitControlEvent('client.ready');
        emitControlEvent('layout.changed', { version: 1, matrix: Array.from(model._modelMatrix.getArray()) });
      }
    },
    handle: async (message: any) => {
      const { name, data = {}, command_id } = message;
      try {
        const now = Date.now();
        const duration = data.duration_ms ?? 5000;
        switch (name) {
          case 'expression.set': {
            const adapter = (window as any).getLAppAdapter?.();
            if (!adapter?.getModel()?._model || adapter.getExpressionCount() < 1) throw new Error('Model is not ready');
            externalState.setExpression(data.name, duration, now);
            adapter.setExpression(externalState.resolveExpression(usePetActivity.getState().sleeping, now));
            break;
          }
          case 'task.start': case 'task.progress': case 'task.end':
            externalState.task(data, now);
            useExternalControl.getState().refresh();
            break;
          case 'subtitle.set': caption(data.text, data.duration_ms ?? 8000, command_id); break;
          case 'speech.say':
            if (data.expression) externalState.setExpression(data.expression, duration, now);
            caption(data.text, data.duration_ms ?? 12000, command_id);
            if (data.audio?.audio) {
              setAiState('thinking-speaking');
              usePetActivity.getState().setActivity('speech', true);
              pendingSpeech.set(command_id, () => {
                if (!pendingSpeech.delete(command_id)) return;
                emitControlEvent('speech.cancelled', {}, command_id);
                if (!pendingSpeech.size) { usePetActivity.getState().setActivity('speech', false); setAiState('idle'); }
              });
              await addAudioTask({ audioBase64: data.audio.audio, volumes: data.audio.volumes,
                sliceLength: data.audio.slice_length, displayText: data.audio.display_text,
                expressions: null, // Expressions are resolved by the app policy, including during audio playback.
                onLifecycle: (event: string) => {
                  if (pendingSpeech.has(command_id)) emitControlEvent(`speech.${event}`, {}, command_id);
                },
                onSettled: () => {
                  pendingSpeech.delete(command_id);
                  if (!pendingSpeech.size) {
                    usePetActivity.getState().setActivity('speech', false);
                    setAiState('idle');
                  }
                },
              });
            } else if (data.speak !== false) throw new Error('No synthesized audio received');
            break;
          case 'ui.visibility': {
            const api = window.api as any;
            if (!api?.setPetVisible) throw new Error('Visibility control requires the desktop app');
            const visible = await api.setPetVisible(data.visible);
            emitControlEvent('ui.visibility', { visible }, command_id); break;
          }
          case 'layout.set': {
            const model = (window as any).getLAppAdapter?.()?.getModel();
            if (!model?._modelMatrix) throw new Error('Model is not ready');
            if (!isPetLayout({ version: 1, matrix: data.matrix })) throw new Error('Invalid transform');
            model._modelMatrix.setMatrix(data.matrix);
            window.dispatchEvent(new CustomEvent('cyrene-layout-restored', { detail: { scale: data.matrix[0] } }));
            window.dispatchEvent(new Event('mouseup')); break;
          }
          case 'interrupt':
            stopAudio(); cancelExternalSpeech(); audioTaskQueue.clearQueue(); setAiState('idle');
            usePetActivity.getState().setActivity('speech', false); break;
          default: throw new Error(`Unsupported desktop command: ${name}`);
        }
        usePetActivity.getState().setActivity('external', externalState.tick(Date.now()));
        emitControlEvent('command.applied', { name }, command_id);
        console.info(`[Cyrene] applied ${name} (${command_id})`);
      } catch (error) {
        emitControlEvent('command.failed', { name, message: String(error) }, command_id);
        console.warn(`[Cyrene] command failed: ${name}: ${error}`);
      }
    },
  };
}
