/**
 * Markdown for the notes fields (shared notes and private notes).
 *
 * This is the Home Keeper approach. The text renders through the `ha-markdown`
 * element of Home Assistant, which parses with `marked` and cleans the HTML with
 * DOMPurify. The bundle has no parser of its own. `ha-markdown` loads lazily, so
 * `ensureMarkdown` asks the card helpers for a markdown card to load it. Until
 * the element is registered, the text shows as escaped plain text.
 */

import { escapeHTML } from './utils';

interface HaMarkdownElement extends HTMLElement {
  content?: string;
}

interface CardHelpers {
  createCardElement?: (config: { type: string; [key: string]: unknown }) => unknown;
}

let pending: Promise<boolean> | undefined;

/** True when `ha-markdown` is registered. */
export function markdownReady(): boolean {
  return Boolean(customElements.get('ha-markdown'));
}

/** Try to register `ha-markdown`. Concurrent callers share 1 attempt. */
export async function ensureMarkdown(timeoutMs = 4000): Promise<boolean> {
  if (markdownReady()) return true;
  if (pending) return pending;
  pending = (async (): Promise<boolean> => {
    try {
      const load = (window as { loadCardHelpers?: () => Promise<CardHelpers> }).loadCardHelpers;
      if (!load) return false;
      const helpers = await load();
      helpers?.createCardElement?.({ type: 'markdown', content: '' });
      await Promise.race([
        customElements.whenDefined('ha-markdown'),
        new Promise((resolve) => setTimeout(resolve, timeoutMs)),
      ]);
      return markdownReady();
    } catch {
      return false;
    }
  })();
  try {
    return await pending;
  } finally {
    pending = undefined;
  }
}

/**
 * The markup that shows *text* as Markdown. The text is in `data-md` (escaped)
 * and `wireMarkdown` moves it to the `content` property after the render.
 * Returns '' for empty text.
 */
export function markdownBlock(text: unknown): string {
  const value = String(text ?? '');
  if (!value) return '';
  if (!markdownReady()) return `<div class="hkl-md hkl-md-plain">${escapeHTML(value)}</div>`;
  return `<ha-markdown breaks class="hkl-md" data-md="${escapeHTML(value)}"></ha-markdown>`;
}

/** Move `data-md` to the `content` property of each `ha-markdown`. Run after each render. */
export function wireMarkdown(root: ParentNode | null | undefined): void {
  root?.querySelectorAll<HaMarkdownElement>('ha-markdown[data-md]').forEach((el) => {
    el.content = el.dataset.md ?? '';
  });
}
