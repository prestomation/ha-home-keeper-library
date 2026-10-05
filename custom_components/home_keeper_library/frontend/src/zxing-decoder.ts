// The barcode decoder for a browser with no native `BarcodeDetector`.
//
// `scanner.ts` imports this module with a dynamic import, so Rollup puts it and
// @zxing/library (Apache-2.0) in a separate chunk. The chunk loads only when the
// scanner opens on such a browser. Only the UPC and EAN readers are imported.

import { HTMLCanvasElementLuminanceSource } from '@zxing/library/esm/browser/HTMLCanvasElementLuminanceSource';
import BarcodeFormat from '@zxing/library/esm/core/BarcodeFormat';
import BinaryBitmap from '@zxing/library/esm/core/BinaryBitmap';
import HybridBinarizer from '@zxing/library/esm/core/common/HybridBinarizer';
import DecodeHintType from '@zxing/library/esm/core/DecodeHintType';
import MultiFormatUPCEANReader from '@zxing/library/esm/core/oned/MultiFormatUPCEANReader';

import type { Detector } from './scanner';

/** A detector that decodes EAN-13, EAN-8 and UPC-A from video frames. */
export function createZxingDetector(): Detector {
  const hints = new Map<DecodeHintType, unknown>();
  hints.set(DecodeHintType.POSSIBLE_FORMATS, [BarcodeFormat.EAN_13, BarcodeFormat.EAN_8, BarcodeFormat.UPC_A]);
  hints.set(DecodeHintType.TRY_HARDER, true);
  const reader = new MultiFormatUPCEANReader(hints);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  return {
    async detect(video: HTMLVideoElement): Promise<string[]> {
      const w = video.videoWidth;
      const h = video.videoHeight;
      if (!w || !h || !ctx) return [];
      // Decode the middle band of the frame, where the frame guide is.
      const bandH = Math.round(h * 0.5);
      canvas.width = w;
      canvas.height = bandH;
      ctx.drawImage(video, 0, Math.round((h - bandH) / 2), w, bandH, 0, 0, w, bandH);
      try {
        const source = new HTMLCanvasElementLuminanceSource(canvas);
        const result = reader.decode(new BinaryBitmap(new HybridBinarizer(source)), hints);
        return [result.getText()];
      } catch {
        return [];
      } finally {
        reader.reset();
      }
    },
  };
}
