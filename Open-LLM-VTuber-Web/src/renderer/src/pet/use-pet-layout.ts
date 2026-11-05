import { useEffect, useRef } from 'react';
import { useMode } from '@/context/mode-context';
import { ModelInfo } from '@/context/live2d-config-context';
import { isPetLayout, readPetLayout, savePetLayout } from './layout';

export function usePetLayout(modelInfo?: ModelInfo) {
  const { mode } = useMode();
  const restoredModel = useRef<unknown>();

  useEffect(() => {
    restoredModel.current = undefined;
    if (mode !== 'pet' || modelInfo?.name !== 'cyrene') return undefined;

    let lastLayout = '';
    const sync = () => {
      const model = (window as any).getLAppAdapter?.()?.getModel();
      if (!model?._modelMatrix || !model?._modelSetting
          || model._textureCount < model._modelSetting.getTextureCount()) return;
      if (restoredModel.current !== model) {
        const fromFile = (window.api as any)?.getSavedPetLayout?.();
        const saved = readPetLayout(window.localStorage) || (isPetLayout(fromFile) ? fromFile : null);
        if (saved) {
          model._modelMatrix.setMatrix(saved.matrix);
          console.info(`[Cyrene] layout restored: scale=${saved.matrix[0]}, x=${saved.matrix[12]}, y=${saved.matrix[13]}`);
        }
        restoredModel.current = model;
        window.dispatchEvent(new CustomEvent('cyrene-layout-restored', {
          detail: { scale: model._modelMatrix.getArray()[0] },
        }));
      }
      const layout = savePetLayout(window.localStorage, model._modelMatrix.getArray());
      if (layout) {
        (window.api as any)?.savePetLayout?.(layout);
        const json = JSON.stringify(layout);
        if (lastLayout !== json) {
          lastLayout = json;
          window.dispatchEvent(new CustomEvent('cyrene-layout-saved', { detail: layout }));
        }
      }
    };
    sync();
    const timer = window.setInterval(sync, 250);
    window.addEventListener('mouseup', sync);
    window.addEventListener('beforeunload', sync);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('mouseup', sync);
      window.removeEventListener('beforeunload', sync);
    };
  }, [mode, modelInfo?.name, modelInfo?.url]);
}
