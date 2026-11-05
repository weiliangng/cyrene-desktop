import { SystemStyleObject } from '@chakra-ui/react';

export const inputSubtitleStyles = {
  container: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'center',
    maxW: 'fit-content',
    position: 'absolute' as const,
    bottom: '48px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 1000,
    userSelect: 'none',
    willChange: 'transform',
    padding: 0,
  },

  box: {
    w: '360px',
    maxW: 'calc(100vw - 32px)',
    rounded: '26px',
    overflow: 'hidden',
    boxShadow: '0 10px 32px rgba(76, 48, 103, 0.16)',
    bg: 'rgba(250, 245, 255, 0.96)',
    border: '1px solid rgba(255, 255, 255, 0.9)',
    css: { WebkitUserSelect: 'none' },
  },

  messageStack: {
    p: '3',
    gap: 1,
    alignItems: 'stretch',
    justify: 'flex-end',
  },

  messageText: {
    color: '#514563',
    fontSize: 'sm',
    lineHeight: '1.5',
    transition: 'all 0.3s',
  },

  statusBox: {
    bg: 'transparent',
    px: '4',
    py: '2',
  },

  statusText: {
    fontSize: 'xs',
    color: '#887496',
    transition: 'all 0.3s',
  },

  iconButton: {
    size: 'xs',
    variant: 'ghost',
    color: '#806994',
    _hover: { bg: '#eee3f7' },
  },

  inputBox: {
    bg: 'transparent',
    px: '1',
    pb: '1',
  },

  input: {
    size: 'sm',
    bg: 'white',
    rounded: 'full',
    px: '4',
    color: '#514563',
    _placeholder: { color: '#a18fad' },
    borderColor: '#e7daef',
    _focus: {
      borderColor: '#c29edb',
      outline: 'none',
    },
    flex: '1',
  },

  sendButton: {
    p: '1.5',
    bg: '#e8d5f5',
    rounded: 'full',
    _hover: { bg: '#dcc1ee' },
    transition: 'colors',
    color: '#76558f',
    size: 'sm',
  },

  draggableContainer: (isDragging: boolean): SystemStyleObject => ({
    cursor: isDragging ? 'grabbing' : 'grab',
    transition: isDragging ? 'none' : 'transform 0.1s ease',
    _active: { cursor: 'grabbing' },
  }),

  closeButton: {
    position: 'absolute' as const,
    top: '5px',
    right: '5px',
    size: '2xs',
    minW: '6',
    height: '6',
    padding: 0,
    variant: 'ghost',
    color: '#a18fad',
    bg: 'transparent',
    _hover: {
      bg: '#eee3f7',
      color: '#76558f',
    },
    zIndex: 10,
  },
} as const;
