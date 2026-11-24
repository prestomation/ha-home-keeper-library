// The confirm dialog. The tab asks through it before each delete, remove and import.
//
// The module holds no tab state. The caller decides what Cancel and the confirm button
// do. The module owns the markup, the keyboard rules and the safe default: Cancel has
// the keyboard, Escape and a tap outside cancel, and Tab stays inside the dialog.
//
// Home Keeper has the same dialog in `confirm-dialog.ts` of its panel. The host API of
// Home Keeper gives a tab no confirm function, so the tab builds its own. The rules and
// the wording are the same. The styles are in `styles.ts` and read `--hkl-*` tokens.

import { t } from './i18n';

/** What the dialog says. The confirm label names the action, for example "Delete book". */
export interface ConfirmContent {
  title: string;
  /** Plain text. A line feed starts a new line. */
  body: string;
  confirmLabel: string;
}

export interface ConfirmHandlers {
  /** Cancel, Escape or a tap outside. */
  onCancel: () => void;
  /** The confirm button. */
  onConfirm: () => void;
}

export interface ConfirmHandle {
  /** Remove the dialog. A second call does nothing. */
  close: () => void;
}

/** Show the dialog inside *parent*, which is the shadow root of the tab. */
export function mountConfirm(parent: ParentNode, content: ConfirmContent, handlers: ConfirmHandlers): ConfirmHandle {
  const scrim = document.createElement('div');
  scrim.className = 'hkl-confirm-scrim';

  const modal = document.createElement('div');
  modal.className = 'hkl-confirm';
  modal.setAttribute('role', 'alertdialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-labelledby', 'hkl-confirm-title');
  modal.setAttribute('aria-describedby', 'hkl-confirm-body');

  const title = document.createElement('h2');
  title.id = 'hkl-confirm-title';
  title.textContent = content.title;

  const body = document.createElement('p');
  body.id = 'hkl-confirm-body';
  body.textContent = content.body;

  const actions = document.createElement('div');
  actions.className = 'hkl-confirm-actions';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'hkl-btn text';
  cancel.dataset.k = 'confirm-cancel';
  cancel.textContent = t('action.cancel');
  cancel.addEventListener('click', () => handlers.onCancel());
  const confirm = document.createElement('button');
  confirm.type = 'button';
  confirm.className = 'hkl-btn danger-primary';
  confirm.dataset.k = 'confirm-ok';
  confirm.textContent = content.confirmLabel;
  confirm.addEventListener('click', () => handlers.onConfirm());
  actions.append(cancel, confirm);

  modal.append(title, body, actions);
  scrim.appendChild(modal);
  scrim.addEventListener('click', (ev) => {
    if (ev.target === scrim) handlers.onCancel();
  });

  // The listener sits on the scrim, so a key never reaches the handlers of the tab
  // below it. Escape closes this dialog and no other.
  const buttons = [cancel, confirm];
  scrim.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') {
      ev.stopPropagation();
      handlers.onCancel();
      return;
    }
    if (ev.key !== 'Tab') return;
    ev.preventDefault();
    ev.stopPropagation();
    const active = (scrim.getRootNode() as Document | ShadowRoot).activeElement as HTMLButtonElement | null;
    const at = active ? buttons.indexOf(active) : -1;
    const next = at < 0 ? (ev.shiftKey ? buttons.length - 1 : 0) : at + (ev.shiftKey ? -1 : 1);
    buttons[(next + buttons.length) % buttons.length].focus();
  });

  parent.appendChild(scrim);
  // Cancel takes the keyboard. It is the safe choice for a delete.
  cancel.focus();

  let open = true;
  return {
    close: () => {
      if (!open) return;
      open = false;
      scrim.remove();
    },
  };
}
