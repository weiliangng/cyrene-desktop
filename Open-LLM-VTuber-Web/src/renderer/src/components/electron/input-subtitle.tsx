import {
  LuBell, LuSend, LuMic, LuMicOff, LuHand, LuX, LuPaperclip,
} from 'react-icons/lu';
import {
  Box,
  Button,
  Flex,
  Textarea,
  Stack,
  Text,
  VStack,
  IconButton,
} from '@chakra-ui/react';
import { useState, useEffect, useCallback } from 'react';
import { useInputSubtitle } from '@/hooks/electron/use-input-subtitle';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { inputSubtitleStyles } from './electron-style';
import { useMode } from '@/context/mode-context';
import { usePetActivity } from '@/pet/use-pet-activity';
import { useChatRun } from '@/pet/chat-run';
import { heldKeys } from '@/pet/cyrene-runtime';
import { useExternalControl, externalState } from '@/pet/external-control';
import { emitControlEvent } from '@/pet/use-cyrene-control';

export function InputSubtitle() {
  const {
    inputValue,
    handleInputChange,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
    handleInterrupt,
    handleMicToggle,
    handleSend,
    handleAttachFiles,
    lastAIMessage,
    hasAIMessages,
    aiState,
    micOn,
  } = useInputSubtitle();

  const { mode } = useMode();
  const isPet = mode === 'pet';
  const { sleeping, setActivity } = usePetActivity();
  const { caption, taskLabel } = useExternalControl();
  const { phase } = useChatRun();
  const expanded = !isPet || !sleeping;

  const {
    elementRef,
    isDragging,
    handleMouseDown,
    handleMouseEnter,
    handleMouseLeave,
  } = useDraggable({
    componentId: 'input-subtitle',
  });

  const [isVisible, setIsVisible] = useState(true);

  const handleClose = useCallback(() => {
    setActivity('panel', false);
    setActivity('focus', false);
    setActivity('draft', false);
    heldKeys.clear();
    if (isPet) {
      (window.api as any)?.updateComponentHover('input-subtitle', false);
    }
    setIsVisible(false);
  }, [isPet, setActivity]);

  const handleOpen = () => {
    setIsVisible(true);
    setActivity('panel', true);
    setActivity('panel', false);
  };

  useEffect(() => {
    setActivity('draft', isVisible && inputValue.trim().length > 0);
  }, [inputValue, isVisible, setActivity]);

  useEffect(() => {
    if (!expanded) (window.api as any)?.updateComponentHover('input-subtitle', false);
  }, [expanded]);

  useEffect(() => {
    const clearKeys = () => { heldKeys.clear(); setActivity('focus', false); setActivity('panel', false); };
    window.addEventListener('blur', clearKeys);
    return () => {
      window.removeEventListener('blur', clearKeys);
      heldKeys.clear();
      setActivity('panel', false);
      setActivity('focus', false);
      setActivity('draft', false);
    };
  }, [setActivity]);

  useEffect(() => {
    if (isPet) {
      const cleanup = (window.api as any)?.onToggleInputSubtitle(() => {
        if (isVisible) {
          handleClose();
        } else {
          handleOpen();
        }
      });
      return () => cleanup?.();
    }
    return () => {};
  }, [handleClose, isPet, isVisible]);

  useEffect(() => {
    (window as any).inputSubtitle = {
      open: handleOpen,
      close: handleClose,
    };

    return () => {
      delete (window as any).inputSubtitle;
    };
  }, [isPet, handleClose]);

  if (!isVisible) return null;

  return (
    <Box
      ref={elementRef}
      {...inputSubtitleStyles.container}
      {...inputSubtitleStyles.draggableContainer(isDragging)}
      style={{ opacity: expanded ? 1 : 0, visibility: expanded ? 'visible' : 'hidden', pointerEvents: expanded ? 'auto' : 'none', transition: 'opacity 180ms ease, visibility 180ms' }}
      aria-hidden={!expanded}
      onMouseDown={(event) => { event.stopPropagation(); handleMouseDown(event); }}
      onMouseEnter={() => { handleMouseEnter(); setActivity('panel', true); }}
      onMouseLeave={() => { handleMouseLeave(); setActivity('panel', false); }}
    >
      <Box {...inputSubtitleStyles.box} style={{ transform: expanded ? 'translateY(0) scale(1)' : 'translateY(8px) scale(0.97)', transition: 'transform 180ms ease' }}>
        <IconButton
          aria-label="Close subtitle"
          onClick={handleClose}
          {...inputSubtitleStyles.closeButton}
        >
          <LuX size={12} />
        </IconButton>

        {(hasAIMessages || caption) && (
          <VStack
            minH={lastAIMessage ? '32px' : '0px'}
            {...inputSubtitleStyles.messageStack}
          >
            {(caption || lastAIMessage) && (
              <Text {...inputSubtitleStyles.messageText}>
                {caption || lastAIMessage}
              </Text>
            )}
          </VStack>
        )}

        <Box {...inputSubtitleStyles.statusBox}>
          <Flex align="center" justify="space-between" color="#887496" pr="4">
            <Flex align="center" gap="2">
              <LuBell size={16} />
              <Text data-testid="cyrene-status" {...inputSubtitleStyles.statusText}>
                {phase === 'stopping' ? 'Stopping…' : taskLabel || (phase === 'running' ? 'Thinking' : aiState === 'idle' ? 'Cyrene' : aiState)}
              </Text>
            </Flex>

            <Flex gap="2">
              <select
                aria-label="Cyrene expression"
                defaultValue=""
                style={{ width: 90, background: 'transparent', color: '#806994', fontSize: 12, border: 0 }}
                onChange={(event) => {
                  externalState.setExpression(event.target.value, 5000, Date.now());
                  event.target.value = '';
                }}
              >
                <option value="" disabled>Expression</option>
                {['neutral', 'happy', 'playful', 'blush', 'star_eyes', 'cry', 'hurt', 'angry', 'sweat', 'confused', 'wink'].map((name) => <option key={name} value={name}>{name.replace('_', ' ')}</option>)}
              </select>
              <IconButton
                aria-label={(window.api as any)?.getMicrophoneEnabled?.() === false ? "Microphone disabled" : "Toggle microphone"}
                disabled={(window.api as any)?.getMicrophoneEnabled?.() === false}
                onClick={handleMicToggle}
                {...inputSubtitleStyles.iconButton}
              >
                {micOn ? <LuMic size={16} /> : <LuMicOff size={16} />}
              </IconButton>
              <IconButton
                aria-label="Interrupt"
                onClick={handleInterrupt}
                {...inputSubtitleStyles.iconButton}
              >
                <LuHand size={16} />
              </IconButton>
            </Flex>
          </Flex>
        </Box>

        <Box {...inputSubtitleStyles.inputBox}>
          <Stack direction="row" gap="2" p="2">
            <IconButton aria-label="Attach file paths" onClick={handleAttachFiles} {...inputSubtitleStyles.iconButton}><LuPaperclip size={16} /></IconButton>
            <Textarea
              rows={2}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={(event) => { heldKeys.add(event.key.toLowerCase()); handleKeyPress(event); }}
              onKeyUp={(event) => heldKeys.delete(event.key.toLowerCase())}
              onFocus={() => { setActivity('focus', true); emitControlEvent('input.focused'); }}
              onBlur={() => { heldKeys.clear(); setActivity('focus', false); emitControlEvent('input.blurred'); }}
              onCompositionStart={handleCompositionStart}
              onCompositionEnd={handleCompositionEnd}
              placeholder="Say something to Cyrene..."
              {...inputSubtitleStyles.input}
              minH="64px"
              resize="vertical"
            />
            <Button
              onClick={handleSend}
              disabled={phase !== 'idle' || aiState === 'thinking-speaking' || !inputValue.trim()}
              {...inputSubtitleStyles.sendButton}
            >
              <LuSend size={16} />
            </Button>
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}
