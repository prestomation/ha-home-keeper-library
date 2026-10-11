// A render helper that keeps the focus and the caret across an innerHTML render.
// Every control has a stable `data-k` attribute for this.

/** The input types that keep what the user types across a render. */
const TEXT_TYPES = ['text', 'search', 'number', 'date'];

/** The elements from the child of *top* down to *el*. */
function pathTo(top: Node, el: Element): Element[] {
  const path: Element[] = [];
  for (let node: Element | null = el; node && node !== top; node = node.parentElement) path.unshift(node);
  return path;
}

function copyAttributes(to: Element, from: Element): void {
  for (const name of to.getAttributeNames()) if (!from.hasAttribute(name)) to.removeAttribute(name);
  for (const name of from.getAttributeNames()) to.setAttribute(name, from.getAttribute(name)!);
}

/**
 * Set *html* into *container*, but keep the element that matches *keep* and its
 * children in the page. The elements on the path to it change in place, and the
 * other elements are replaced. A browser can pause a video that leaves the page,
 * so this keeps the camera video in the page. Returns false, with no change, if the old or
 * the new markup has no such element, or if the 2 paths have different tags.
 */
export function replaceKeeping(container: HTMLElement, html: string, keep: string): boolean {
  const old = container.querySelector(keep);
  const tpl = document.createElement('template');
  tpl.innerHTML = html;
  const neu = tpl.content.querySelector(keep);
  if (!old || !neu) return false;
  const oldPath = pathTo(container, old);
  const newPath = pathTo(tpl.content, neu);
  if (oldPath.length !== newPath.length || oldPath.some((el, i) => el.tagName !== newPath[i].tagName)) return false;
  let newParent: ParentNode = tpl.content;
  oldPath.forEach((o, i) => {
    const n = newPath[i];
    const kids = [...newParent.childNodes];
    const at = kids.indexOf(n);
    for (const c of [...o.parentNode!.childNodes]) if (c !== o) c.remove();
    o.before(...kids.slice(0, at));
    o.after(...kids.slice(at + 1));
    copyAttributes(o, n);
    newParent = n;
  });
  return true;
}

/**
 * Set *html* into *container* and give the focus back to the same control. The
 * focused text field also keeps its value, so a render that a store change or a
 * camera error starts does not remove what the user is typing. If *keep* is a
 * selector, the element that matches it stays in the page (`replaceKeeping`).
 */
export function renderKeepFocus(root: ShadowRoot, container: HTMLElement, html: string, keep?: string): void {
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
  if (!keep || !replaceKeeping(container, html, keep)) container.innerHTML = html;
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
