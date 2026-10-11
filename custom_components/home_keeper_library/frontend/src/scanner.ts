// The camera scanner: `getUserMedia` and a barcode detector.
//
// The native `BarcodeDetector` is used when it supports a book format. Else the
// zxing chunk loads (see `zxing-decoder.ts`). The camera API needs a secure
// origin (HTTPS), so `start` reports "insecure" when `navigator.mediaDevices`
// is missing.
//
// The camera log keeps the last camera events for the debug view (`;debug=1`).
// It is in the module, so it stays when Home Keeper makes a new tab element.

export interface Detector {
  detect(video: HTMLVideoElement): Promise<string[]>;
}

export type StartResult = 'ok' | 'insecure' | 'denied' | 'unsupported';

const LOG_SIZE = 12;
const logStart = Date.now();
const camLog: string[] = [];

/** Add a line to the camera log. */
export function logCam(msg: string): void {
  camLog.push(`${((Date.now() - logStart) / 1000).toFixed(1)}s ${msg}`);
  if (camLog.length > LOG_SIZE) camLog.shift();
}

/** The camera log, oldest line first. */
export function camLogLines(): string[] {
  return [...camLog];
}

/** The name and message of an error, for the camera log. */
function errName(err: unknown): string {
  return err instanceof Error ? `${err.name}: ${err.message}` : String(err);
}

/** True when the page is not secure (an `http://` address), so the browser gives no camera. */
export function cameraNeedsHttps(): boolean {
  return globalThis.isSecureContext === false;
}

const BOOK_FORMATS = ['ean_13', 'ean_8', 'upc_a'];
/** A playing video whose time does not move for this long has a frozen picture. */
export const FROZEN_MS = 1500;

interface NativeDetector {
  detect(source: HTMLVideoElement): Promise<Array<{ rawValue: string }>>;
}
interface NativeDetectorClass {
  new (opts: { formats: string[] }): NativeDetector;
  getSupportedFormats?: () => Promise<string[]>;
}

/** The native detector, or the zxing detector from a lazy chunk. */
export async function createDetector(): Promise<Detector & { kind: string }> {
  const Native = (window as unknown as { BarcodeDetector?: NativeDetectorClass }).BarcodeDetector;
  if (Native) {
    try {
      const supported = (await Native.getSupportedFormats?.()) ?? BOOK_FORMATS;
      const formats = BOOK_FORMATS.filter((f) => supported.includes(f));
      if (formats.length) {
        const native = new Native({ formats });
        return { kind: 'native', detect: async (video) => (await native.detect(video)).map((r) => r.rawValue) };
      }
    } catch {
      // Use the zxing chunk.
    }
  }
  const mod = await import('./zxing-decoder');
  return { kind: 'zxing', ...mod.createZxingDetector() };
}

/**
 * A running camera that calls `onCode` for each barcode it reads. It calls
 * `onState` when the picture can stop or start again: a video or track event,
 * or a refused `play()`.
 */
export class Scanner {
  readonly video: HTMLVideoElement;
  private stream: MediaStream | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private detector: (Detector & { kind?: string }) | null = null;
  private busy = false;
  private stopped = true;
  private playError = '';
  private decodes = 0;
  private lastTime = -1;
  private lastMove = 0;
  private frozen = false;
  private readonly counts: Record<string, number> = {};

  constructor(
    private readonly onCode: (code: string) => void,
    private readonly intervalMs = 180,
    private readonly onState: () => void = () => undefined,
  ) {
    this.video = document.createElement('video');
    this.video.setAttribute('playsinline', '');
    this.video.muted = true;
    this.video.autoplay = true;
    for (const name of ['pause', 'playing', 'emptied']) {
      this.video.addEventListener(name, () => this.event(`video ${name}`));
    }
  }

  private event(name: string): void {
    if (this.stopped) return;
    this.counts[name] = (this.counts[name] ?? 0) + 1;
    if (name === 'video playing') this.playError = '';
    logCam(name);
    this.onState();
  }

  async start(): Promise<StartResult> {
    if (!this.stopped) return 'ok';
    const media = navigator.mediaDevices;
    if (!media?.getUserMedia) return cameraNeedsHttps() ? 'insecure' : 'unsupported';
    try {
      this.stream = await media.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
    } catch (err) {
      logCam(`getUserMedia ${errName(err)}`);
      return 'denied';
    }
    logCam('getUserMedia ok');
    this.stopped = false;
    for (const track of this.stream.getVideoTracks()) {
      for (const name of ['ended', 'mute', 'unmute']) track.addEventListener(name, () => this.event(`track ${name}`));
    }
    this.video.srcObject = this.stream;
    void this.play();
    try {
      this.detector = await createDetector();
    } catch (err) {
      logCam(`detector ${errName(err)}`);
      this.stop();
      return 'unsupported';
    }
    this.loop();
    return 'ok';
  }

  /** Find a frozen picture: the video plays and had a frame, but its time does not move. */
  private checkFrozen(): void {
    const now = Date.now();
    if (this.video.paused || this.video.readyState < 2 || this.video.currentTime !== this.lastTime) {
      this.lastTime = this.video.currentTime;
      this.lastMove = now;
      if (this.frozen) {
        this.frozen = false;
        this.event('video moves');
      }
    } else if (!this.frozen && now - this.lastMove > FROZEN_MS) {
      this.frozen = true;
      this.event('video frozen');
    }
  }

  private loop(): void {
    if (this.stopped) return;
    this.timer = setTimeout(async () => {
      if (this.stopped) return;
      this.checkFrozen();
      if (!this.busy && this.detector && this.video.readyState >= 2) {
        this.busy = true;
        try {
          for (const code of await this.detector.detect(this.video)) {
            this.decodes++;
            this.onCode(code);
          }
        } catch {
          // A frame that fails to decode is normal.
        } finally {
          this.busy = false;
        }
      }
      this.loop();
    }, this.intervalMs);
  }

  /** Play the video. A refused `play()` goes in the log and calls `onState`. True if it plays. */
  private play(): Promise<boolean> {
    return this.video.play().then(
      () => true,
      (err: unknown) => {
        if (this.stopped) return false;
        this.playError = errName(err);
        logCam(`play() ${this.playError}`);
        this.onState();
        return false;
      },
    );
  }

  /** Play the video again if it is paused, for example after it moved in the page. True if it plays. */
  resume(): Promise<boolean> {
    if (this.stopped) return Promise.resolve(false);
    return this.video.paused ? this.play() : Promise.resolve(true);
  }

  /** True if the camera track ended. Then only a new `start` gives a picture. */
  ended(): boolean {
    const track = this.stream?.getVideoTracks()[0];
    return !this.stopped && (!track || track.readyState === 'ended');
  }

  /** True if the video plays but its picture is frozen. Then only a new `start` can help. */
  isFrozen(): boolean {
    return !this.stopped && this.frozen;
  }

  /** True if the camera runs but the picture does not move. */
  stalled(): boolean {
    return !this.stopped && (this.ended() || this.video.paused || this.frozen);
  }

  /** The camera state as lines of text, for the debug view. */
  debugLines(): string[] {
    const v = this.video;
    const track = this.stream?.getVideoTracks()[0];
    const counts = Object.entries(this.counts).map(([k, n]) => `${k}=${n}`).join(' ');
    return [
      `video: paused=${v.paused} frozen=${this.frozen} ready=${v.readyState} src=${v.srcObject ? 'yes' : 'no'} size=${v.videoWidth}x${v.videoHeight} t=${v.currentTime.toFixed(1)} in page=${v.isConnected}`,
      `track: ${track ? `${track.readyState} muted=${track.muted} enabled=${track.enabled}` : 'none'}`,
      `detector: ${this.detector?.kind ?? 'none'} codes=${this.decodes}`,
      `events: ${counts || 'none'}`,
      `play error: ${this.playError || 'none'}`,
    ];
  }

  /** True if the camera track has a torch. */
  torchSupported(): boolean {
    const track = this.stream?.getVideoTracks()[0];
    const caps = (track?.getCapabilities?.() ?? {}) as { torch?: boolean };
    return Boolean(caps.torch);
  }

  async setTorch(on: boolean): Promise<void> {
    const track = this.stream?.getVideoTracks()[0];
    await track?.applyConstraints({ advanced: [{ torch: on } as MediaTrackConstraintSet] });
  }

  stop(): void {
    if (!this.stopped) logCam('stop');
    this.stopped = true;
    if (this.timer !== undefined) clearTimeout(this.timer);
    this.timer = undefined;
    this.stream?.getTracks().forEach((tr) => tr.stop());
    this.stream = null;
    this.video.srcObject = null;
  }
}
