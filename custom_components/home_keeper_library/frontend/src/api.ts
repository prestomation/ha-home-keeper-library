// The websocket client for the tab and the card.
//
// Each command name is `home_keeper_library/<service>` with the same fields as
// the service (build spec, section 5). The backend applies the same admin gate
// and the same read projection as the service.

import type { HomeAssistant, ImportSummary, RawState, ScanResult } from './types';

export const DOMAIN = 'home_keeper_library';

/** The authenticated upload view for a custom cover (POST multipart, field `file`). */
export const UPLOAD_URL = `/api/${DOMAIN}/upload`;

/** The largest CSV file that `import_csv` accepts. */
export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;

/** The largest cover image that the upload view accepts. */
export const MAX_COVER_BYTES = 10 * 1024 * 1024;

export type Fields = Record<string, unknown>;

/** Remove the keys whose value is undefined, so the backend applies its default. */
export function compact(fields: Fields): Fields {
  const out: Fields = {};
  for (const [key, value] of Object.entries(fields)) if (value !== undefined) out[key] = value;
  return out;
}

export class LibraryApi {
  constructor(private hass: HomeAssistant) {}

  setHass(hass: HomeAssistant): void {
    this.hass = hass;
  }

  /** Send 1 command and return its result. */
  call<T = unknown>(command: string, fields: Fields = {}): Promise<T> {
    return this.hass.connection.sendMessagePromise<T>({
      type: `${DOMAIN}/${command}`,
      ...compact(fields),
    });
  }

  getState(): Promise<RawState> {
    return this.call<RawState>('get_state');
  }

  /** Call *onChange* after each store change. Returns the unsubscribe function. */
  subscribe(onChange: (revision: unknown) => void): Promise<() => void | Promise<void>> {
    return this.hass.connection.subscribeMessage<{ type?: string; revision?: unknown }>(
      (msg) => {
        if (!msg || msg.type === 'changed') onChange(msg?.revision);
      },
      { type: `${DOMAIN}/subscribe` },
    );
  }

  scanIsbn(fields: Fields): Promise<ScanResult> {
    return this.call<ScanResult>('scan_isbn', fields);
  }

  importCsv(fields: Fields): Promise<ImportSummary> {
    return this.call<ImportSummary>('import_csv', fields);
  }

  exportCsv(fields: Fields): Promise<{ filename: string; content: string }> {
    return this.call('export_csv', fields);
  }

  async listTodoEntities(): Promise<Array<{ entity_id: string; name?: string }>> {
    const res = await this.call<unknown>('list_todo_entities');
    const list = Array.isArray(res) ? res : ((res as { entities?: unknown[] })?.entities ?? []);
    return (list as Array<string | { entity_id: string; name?: string }>).map((e) =>
      typeof e === 'string' ? { entity_id: e } : e,
    );
  }

  /** Upload a cover image and return its `file_id` for `set_cover`. */
  async uploadCover(file: File): Promise<string> {
    if (!this.hass.fetchWithAuth) throw new Error('upload not available');
    const body = new FormData();
    body.append('file', file);
    const res = await this.hass.fetchWithAuth(UPLOAD_URL, { method: 'POST', body });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    const data = (await res.json()) as { file_id?: string };
    if (!data.file_id) throw new Error('no file_id');
    return data.file_id;
  }
}

/** The text of a websocket error, for a toast or an inline message. */
export function errorText(err: unknown): string {
  if (err && typeof err === 'object' && 'message' in err) {
    return String((err as { message: unknown }).message);
  }
  return String(err);
}
