// A render helper that keeps the focus and the caret across an innerHTML render.
// Every control has a stable `data-k` attribute for this.

/** The input types that keep what the user types across a render. */
const TEXT_TYPES = ['text', 'search', 'number', 'date'];

/**
 * Set *html* into *container* and give the focus back to the same control. The
 * focused text field also keeps its value, so a render that a store change or a
 * camera error starts does not remove what the user is typing.
 */
export function renderKeepFocus(root: ShadowRoot, container: HTMLElement, html: string): void {
  const active = root.activeElement as HTMLElement | null;
  const inside = Boolean(active && container.contains(active));
  const key = inside ? active?.dataset.k : undefined;
  let sel: [number | null, number | null] | null = null;
  let typed: string | null = null;
  if (inside && active instanceof HTMLInputElement && TEXT_TYPES.includes(active.type)) {
    typed = active.value;
    if (['text', 'search'].includes(active.type)) sel = [active.selectionStart, active.selectionEnd];
  } else if (inside && active instanceof HTMLTextAreaElement) {
    typed = active.value;
  }
  container.innerHTML = html;
  if (!key) return;
  const el = container.querySelector<HTMLElement>(`[data-k="${CSS.escape(key)}"]`);
  if (!el) return;
  if (typed !== null && (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) && el.type === (active as HTMLInputElement).type) {
    el.value = typed;
  }
  el.focus();
  if (sel && el instanceof HTMLInputElement) {
    try {
      el.setSelectionRange(sel[0], sel[1]);
    } catch {
      // Some input types have no selection.
    }
  }
}
