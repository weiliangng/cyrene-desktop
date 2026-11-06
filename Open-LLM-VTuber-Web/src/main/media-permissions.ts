// Audio capture and output sound are independent permissions.
export function allowsMediaCapture(microphoneEnabled: boolean, mediaTypes?: string[]): boolean {
  if (microphoneEnabled) return true;
  // Unknown/combined requests must not implicitly enable microphone capture.
  return Boolean(mediaTypes?.length && mediaTypes.every((type) => type === 'video'));
}
