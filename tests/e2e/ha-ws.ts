/**
 * A small Home Assistant websocket client for the setup and the helpers of the
 * browser tests. It runs in Node (Node 22 has a global `WebSocket`), not in the page.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export const HA_URL = process.env.HA_URL || 'http://localhost:8123';

export interface HaWs {
  call<T = unknown>(msg: Record<string, unknown>): Promise<T>;
  close(): void;
}

/** Open a websocket, sign in with *token* and return a `call` for commands. */
export async function haWs(token: string): Promise<HaWs> {
  const ws = new WebSocket(`${HA_URL.replace(/^http/, 'ws')}/api/websocket`);
  const pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  let next = 1;
  await new Promise<void>((ok, fail) => {
    ws.onerror = () => fail(new Error('websocket error'));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(String(ev.data));
      if (msg.type === 'auth_required') ws.send(JSON.stringify({ type: 'auth', access_token: token }));
      else if (msg.type === 'auth_ok') ok();
      else if (msg.type === 'auth_invalid') fail(new Error(`auth_invalid: ${msg.message}`));
      else if (msg.type === 'result') {
        const p = pending.get(msg.id);
        if (!p) return;
        pending.delete(msg.id);
        if (msg.success) p.resolve(msg.result);
        else p.reject(new Error(`${msg.error?.code}: ${msg.error?.message}`));
      }
    };
  });
  return {
    call<T>(msg: Record<string, unknown>): Promise<T> {
      const id = next++;
      return new Promise<T>((ok, fail) => {
        pending.set(id, { resolve: ok as (v: unknown) => void, reject: fail });
        ws.send(JSON.stringify({ id, ...msg }));
      });
    },
    close: () => ws.close(),
  };
}

/** A new access token from a refresh token. */
export async function accessToken(refreshToken: string): Promise<string> {
  const r = await fetch(`${HA_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'refresh_token', refresh_token: refreshToken, client_id: `${HA_URL}/` }),
  });
  if (!r.ok) throw new Error(`token refresh failed: ${r.status}`);
  return ((await r.json()) as { access_token: string }).access_token;
}

/** Run *fn* with a websocket of Alex (`admin`) or Sam (`user`). */
export async function withWs<T>(who: 'admin' | 'user', fn: (ws: HaWs) => Promise<T>): Promise<T> {
  const tokens = JSON.parse(readFileSync(resolve(__dirname, '.auth/token.json'), 'utf8')) as Record<string, string>;
  const ws = await haWs(await accessToken(tokens[who]));
  try {
    return await fn(ws);
  } finally {
    ws.close();
  }
}

/** A `home_keeper_library/<command>` call as Alex. */
export function library<T = unknown>(command: string, fields: Record<string, unknown> = {}): Promise<T> {
  return withWs('admin', (ws) => ws.call<T>({ type: `home_keeper_library/${command}`, ...fields }));
}
