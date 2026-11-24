import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mountConfirm } from '../src/confirm-dialog.ts';

// The confirm dialog is 1 module for every delete, remove and import of the tab.

let host;
let handle;
const content = { title: 'Delete "Dune"?', body: 'Copies: 2\nYou cannot undo this.', confirmLabel: 'Delete book' };

function mount(handlers = {}) {
  const h = { onCancel: vi.fn(), onConfirm: vi.fn(), ...handlers };
  handle = mountConfirm(host, content, h);
  return h;
}
const $ = (sel) => host.querySelector(sel);
const key = (k, init = {}) => {
  const ev = new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...init });
  $('.hkl-confirm-scrim').dispatchEvent(ev);
  return ev;
};

beforeEach(() => {
  host = document.createElement('div');
  host.attachShadow({ mode: 'open' });
  document.body.appendChild(host);
  host = host.shadowRoot;
});
afterEach(() => {
  handle?.close();
  handle = undefined;
  host.host.remove();
});

describe('mountConfirm', () => {
  it('is an alertdialog with a name and a description', () => {
    mount();
    const modal = $('[role="alertdialog"]');
    expect(modal.getAttribute('aria-modal')).toBe('true');
    expect(host.getElementById(modal.getAttribute('aria-labelledby')).textContent).toBe('Delete "Dune"?');
    expect(host.getElementById(modal.getAttribute('aria-describedby')).textContent).toBe('Copies: 2\nYou cannot undo this.');
    expect($('[data-k="confirm-ok"]').textContent).toBe('Delete book');
    expect($('[data-k="confirm-ok"]').classList.contains('danger-primary')).toBe(true);
  });

  it('puts the focus on Cancel', () => {
    mount();
    expect(host.activeElement).toBe($('[data-k="confirm-cancel"]'));
    expect($('[data-k="confirm-cancel"]').textContent).toBe('Cancel');
  });

  it('calls onConfirm only for the confirm button', () => {
    const h = mount();
    $('[data-k="confirm-ok"]').click();
    expect(h.onConfirm).toHaveBeenCalledTimes(1);
    expect(h.onCancel).not.toHaveBeenCalled();
  });

  it('cancels on Cancel, on Escape and on a tap outside, and not on a tap inside', () => {
    const h = mount();
    $('[data-k="confirm-cancel"]').click();
    const seen = vi.fn();
    host.addEventListener('keydown', seen);
    key('Escape');
    expect(seen).not.toHaveBeenCalled();
    $('.hkl-confirm-scrim').click();
    expect(h.onCancel).toHaveBeenCalledTimes(3);
    $('.hkl-confirm').click();
    expect(h.onCancel).toHaveBeenCalledTimes(3);
    expect(h.onConfirm).not.toHaveBeenCalled();
  });

  it('keeps Tab inside the dialog', () => {
    mount();
    const cancel = $('[data-k="confirm-cancel"]');
    const ok = $('[data-k="confirm-ok"]');
    expect(key('Tab').defaultPrevented).toBe(true);
    expect(host.activeElement).toBe(ok);
    key('Tab');
    expect(host.activeElement).toBe(cancel);
    key('Tab', { shiftKey: true });
    expect(host.activeElement).toBe(ok);
  });

  it('removes itself, and a second close does nothing', () => {
    mount();
    handle.close();
    expect($('.hkl-confirm-scrim')).toBeNull();
    expect(() => handle.close()).not.toThrow();
  });

  it('shows text as text, never as markup', () => {
    handle = mountConfirm(host, { ...content, title: '<img src=x onerror=1>' }, { onCancel() {}, onConfirm() {} });
    expect($('h2').textContent).toBe('<img src=x onerror=1>');
    expect($('h2 img')).toBeNull();
  });

  it('uses buttons that do not submit a form, with the styles of the tab', () => {
    mount();
    expect($('.hkl-confirm-actions')).not.toBeNull();
    expect([...host.querySelectorAll('button')].map((b) => [b.type, b.className])).toEqual([
      ['button', 'hkl-btn text'],
      ['button', 'hkl-btn danger-primary'],
    ]);
  });

  it('starts Tab at the first button, and Shift+Tab at the last, if no button has the focus', () => {
    mount();
    const cancel = $('[data-k="confirm-cancel"]');
    const ok = $('[data-k="confirm-ok"]');
    cancel.blur();
    key('Tab');
    expect(host.activeElement).toBe(cancel);
    cancel.blur();
    key('Tab', { shiftKey: true });
    expect(host.activeElement).toBe(ok);
    // Wraps from the last button to the first.
    key('Tab');
    expect(host.activeElement).toBe(cancel);
  });

  it('keeps a Tab key from reaching the tab below', () => {
    mount();
    const seen = vi.fn();
    host.addEventListener('keydown', seen);
    key('Tab');
    key('a');
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it('removes the scrim at the first close and not before', () => {
    mount();
    expect($('.hkl-confirm-scrim')).not.toBeNull();
    handle.close();
    expect(host.querySelectorAll('.hkl-confirm-scrim')).toHaveLength(0);
    // A second dialog opened after the close stays after a stale close.
    const second = mountConfirm(host, content, { onCancel() {}, onConfirm() {} });
    handle.close();
    expect($('.hkl-confirm-scrim')).not.toBeNull();
    second.close();
  });
});
