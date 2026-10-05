/** Config for the video walkthrough (see walkthrough.capture.ts and ci/capture-video.sh). */
import { captureConfig } from './capture-config';

export default captureConfig('walkthrough.capture.ts', {
  // The tour is about 45 s of beats and actions. 180 s leaves room for a slow
  // runner. A tour that needs more is too long: drop a beat before this moves.
  timeout: 180_000,
  use: {
    // A bad selector fails fast and names its step, not the whole tour.
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },
});
