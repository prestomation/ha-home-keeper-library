// A fake `hass` for the DOM tests. `connection.sendMessagePromise` answers from a
// copy of `fixtures/state.json`, and `subscribeMessage` keeps the callback so a
// test can push a `changed` message.
import { vi } from 'vitest';
import FIXTURE from './fixtures/state.json';

export const ALEX = FIXTURE.me.person_id;
export const SAM = 'sam';
export const JO = 'jo';

export function fixture() {
  return structuredClone(FIXTURE);
}

export function bookId(state, title) {
  return Object.values(state.books).find((b) => b.title === title).id;
}

export function fakeHass({ state = fixture(), replies = {}, language = 'en', callApi } = {}) {
  const subs = [];
  const send = vi.fn(async (msg) => {
    const cmd = msg.type.replace('home_keeper_library/', '');
    if (cmd === 'get_state') return structuredClone(state);
    if (msg.type === 'auth/sign_path' && !('auth/sign_path' in replies)) return { path: `${msg.path}&authSig=t${msg.expires}` };
    if (cmd in replies) {
      const r = replies[cmd];
      return typeof r === 'function' ? r(msg) : r;
    }
    return {};
  });
  const hass = {
    language,
    callApi,
    states: {
      'person.alex': { entity_id: 'person.alex', state: 'home', attributes: { id: ALEX, friendly_name: 'Alex' } },
      'person.sam': { entity_id: 'person.sam', state: 'home', attributes: { id: SAM, friendly_name: 'Sam' } },
      'person.jo': { entity_id: 'person.jo', state: 'home', attributes: { id: JO, friendly_name: 'Jo' } },
    },
    areas: { living_room: { area_id: 'living_room', name: 'Living Room' } },
    connection: {
      sendMessagePromise: send,
      subscribeMessage: vi.fn(async (cb, msg) => {
        subs.push({ cb, msg });
        return () => undefined;
      }),
    },
  };
  return {
    hass,
    send,
    state,
    subs,
    push: () => subs.forEach((s) => s.cb({ type: 'changed', revision: 2 })),
    calls: (cmd) => send.mock.calls.map((c) => c[0]).filter((m) => m.type === `home_keeper_library/${cmd}`),
  };
}

/** Let pending promises and timers of 0 ms run. */
export async function flush(times = 6) {
  for (let i = 0; i < times; i++) await new Promise((r) => setTimeout(r, 0));
}
