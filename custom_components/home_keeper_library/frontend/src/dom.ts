// A render helper that keeps the focus and the caret across an innerHTML render.
// Every control has a stable `data-k` attribute for this.

/** Set *html* into *container* and give the focus back to the same control. */
export function renderKeepFocus(root: ShadowRoot, container: HTMLElement, html: string): void {
  const active = root.activeElement as HTMLElement | null;
  const inside = Boolean(active && container.contains(active));
  const key = inside ? active?.dataset.k : undefined;
  let sel: [number | null, number | null] | null = null;
  if (inside && active instanceof HTMLInputElement && ['text', 'search'].includes(active.type)) {
    sel = [active.selectionStart, active.selectionEnd];
  }
  container.innerHTML = html;
  if (!key) return;
  const el = container.querySelector<HTMLElement>(`[data-k="${CSS.escape(key)}"]`);
  if (!el) return;
  el.focus();
  if (sel && el instanceof HTMLInputElement) {
    try {
      el.setSelectionRange(sel[0], sel[1]);
    } catch {
      // Some input types have no selection.
    }
  }
}
