// The camera scanner: `getUserMedia` and a barcode detector.
//
// The native `BarcodeDetector` is used when it supports a book format. Else the
// zxing chunk loads (see `zxing-decoder.ts`). The camera API needs a secure
// origin (HTTPS), so `start` reports "insecure" when `navigator.mediaDevices`
// is missing.

export interface Detector {
  detect(video: HTMLVideoElement): Promise<string[]>;
}

export type StartResult = 'ok' | 'insecure' | 'denied' | 'unsupported';

const BOOK_FORMATS = ['ean_13', 'ean_8', 'upc_a'];

interface NativeDetector {
  detect(source: HTMLVideoElement): Promise<Array<{ rawValue: string }>>;
}
interface NativeDetectorClass {
  new (opts: { formats: string[] }): NativeDetector;
  getSupportedFormats?: () => Promise<string[]>;
}

/** The native detector, or the zxing detector from a lazy chunk. */
export async function createDetector(): Promise<Detector> {
  const Native = (window as unknown as { BarcodeDetector?: NativeDetectorClass }).BarcodeDetector;
  if (Native) {
    try {
      const supported = (await Native.getSupportedFormats?.()) ?? BOOK_FORMATS;
      const formats = BOOK_FORMATS.filter((f) => supported.includes(f));
      if (formats.length) {
        const native = new Native({ formats });
        return { detect: async (video) => (await native.detect(video)).map((r) => r.rawValue) };
      }
    } catch {
      // Use the zxing chunk.
    }
  }
  const mod = await import('./zxing-decoder');
  return mod.createZxingDetector();
}

/** A running camera that calls `onCode` for each barcode it reads. */
export class Scanner {
  readonly video: HTMLVideoElement;
  private stream: MediaStream | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private detector: Detector | null = null;
  private busy = false;
  private stopped = true;

  constructor(private readonly onCode: (code: string) => void, private readonly intervalMs = 180) {
    this.video = document.createElement('video');
    this.video.setAttribute('playsinline', '');
    this.video.muted = true;
    this.video.autoplay = true;
  }

  get running(): boolean {
    return !this.stopped;
  }

  async start(): Promise<StartResult> {
    if (!this.stopped) return 'ok';
    const media = navigator.mediaDevices;
    if (!media?.getUserMedia) return window.isSecureContext === false ? 'insecure' : 'unsupported';
    try {
      this.stream = await media.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
    } catch {
      return 'denied';
    }
    this.stopped = false;
    this.video.srcObject = this.stream;
    void this.video.play().catch(() => undefined);
    try {
      this.detector = await createDetector();
    } catch {
      this.stop();
      return 'unsupported';
    }
    this.loop();
    return 'ok';
  }

  private loop(): void {
    if (this.stopped) return;
    this.timer = setTimeout(async () => {
      if (this.stopped) return;
      if (!this.busy && this.detector && this.video.readyState >= 2) {
        this.busy = true;
        try {
          for (const code of await this.detector.detect(this.video)) this.onCode(code);
        } catch {
          // A frame that fails to decode is normal.
        } finally {
          this.busy = false;
        }
      }
      this.loop();
    }, this.intervalMs);
  }

  /** Play the video again after it moves to a new parent element. */
  resume(): void {
    if (!this.stopped) void this.video.play().catch(() => undefined);
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
    this.stopped = true;
    if (this.timer !== undefined) clearTimeout(this.timer);
    this.timer = undefined;
    this.stream?.getTracks().forEach((tr) => tr.stop());
    this.stream = null;
    this.video.srcObject = null;
  }
}
