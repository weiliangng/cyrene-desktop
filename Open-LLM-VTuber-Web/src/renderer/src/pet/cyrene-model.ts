export const cyreneModel = {
  name: 'cyrene',
  url: typeof window !== 'undefined' && window.api
    ? 'cyrene://assets/cyrene/cyrene.model3.json'
    : 'http://127.0.0.1:12393/live2d-models/cyrene/cyrene.model3.json',
  kScale: 1.1,
  initialXshift: 0,
  initialYshift: 0,
  defaultEmotion: 'sleep',
  emotionMap: {
    neutral: 'neutral', joy: 'happy', anger: 'angry', sadness: 'cry',
    shy: 'blush', playful: 'playful', excited: 'star_eyes', hurt: 'hurt',
    sleepy: 'sleep', nervous: 'sweat', surprise: 'confused', wink: 'wink',
  },
  tapMotions: {},
};
