/**
 * Playwright global setup: the users, the people and the sign-in of the browser tests.
 *
 * 1. Complete onboarding as Alex (user `test`, an admin), or sign in when an earlier
 *    run did it. Onboarding gives Alex the person id `alex`.
 * 2. Add Sam, a user who is not an admin, with the person id `sam`, Jo, a person
 *    with no user, with the person id `jo`, and the area `office`. The seed library
 *    (tests/e2e/seed/build_seed.py) uses these 3 ids.
 * 3. Wait until the library is loaded, then write a storage state for Alex
 *    (`.auth/state.json`, the default) and for Sam (`.auth/sam.json`), and the
 *    access token of Alex (`.auth/token.json`) for the helpers.
 *
 * Home Assistant makes a person id from the name, so the ids are fixed. The setup
 * fails when an id is not the one that the seed expects.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { haWs, HA_URL } from './ha-ws';

const CLIENT_ID = `${HA_URL}/`;
const AUTH_DIR = resolve(__dirname, '.auth');
export const ADMIN = { username: 'test', password: 'testtest1', name: 'Alex', person: 'alex' };
export const USER = { username: 'sam', password: 'samsam123', name: 'Sam', person: 'sam' };
export const NO_USER = { name: 'Jo', person: 'jo' };

interface Tokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

async function waitForHA(timeoutMs = 180_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${HA_URL}/api/`);
      if (r.status === 200 || r.status === 401) return;
    } catch {
      // Not up yet.
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`Home Assistant did not answer within ${timeoutMs} ms at ${HA_URL}`);
}

async function exchange(code: string): Promise<Tokens> {
  const r = await fetch(`${HA_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'authorization_code', code, client_id: CLIENT_ID }),
  });
  if (!r.ok) throw new Error(`token exchange failed: ${r.status} ${await r.text()}`);
  return (await r.json()) as Tokens;
}

/** Sign in with the login flow of Home Assistant. */
export async function login(username: string, password: string): Promise<Tokens> {
  const flow = await (
    await fetch(`${HA_URL}/auth/login_flow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: CLIENT_ID, handler: ['homeassistant', null], redirect_uri: CLIENT_ID }),
    })
  ).json();
  const step = await (
    await fetch(`${HA_URL}/auth/login_flow/${flow.flow_id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: CLIENT_ID, username, password }),
    })
  ).json();
  if (step.type !== 'create_entry') throw new Error(`login of ${username} failed: ${JSON.stringify(step)}`);
  return exchange(step.result);
}

async function onboardAdmin(): Promise<Tokens> {
  const r = await fetch(`${HA_URL}/api/onboarding/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: CLIENT_ID, name: ADMIN.name, username: ADMIN.username, password: ADMIN.password, language: 'en' }),
  });
  if (!r.ok) return login(ADMIN.username, ADMIN.password);
  const tokens = await exchange((await r.json()).auth_code);
  const auth = { Authorization: `Bearer ${tokens.access_token}`, 'Content-Type': 'application/json' };
  for (const step of ['core_config', 'analytics', 'integration']) {
    await fetch(`${HA_URL}/api/onboarding/${step}`, {
      method: 'POST',
      headers: auth,
      body: JSON.stringify(step === 'integration' ? { client_id: CLIENT_ID, redirect_uri: CLIENT_ID } : {}),
    });
  }
  return tokens;
}

interface PersonRow {
  id: string;
  name: string;
  user_id: string | null;
}

/** Add Sam (with a user) and Jo (with no user) if they are not there. */
async function ensurePeople(token: string): Promise<void> {
  const ws = await haWs(token);
  try {
    const listed = await ws.call<{ storage: PersonRow[] }>({ type: 'person/list' });
    const byName = new Map(listed.storage.map((p) => [p.name, p]));
    if (!byName.has(USER.name)) {
      const user = await ws.call<{ user: { id: string } }>({
        type: 'config/auth/create',
        name: USER.name,
        group_ids: ['system-users'],
        local_only: false,
      });
      await ws.call({
        type: 'config/auth_provider/homeassistant/create',
        user_id: user.user.id,
        username: USER.username,
        password: USER.password,
      });
      byName.set(USER.name, await ws.call<PersonRow>({ type: 'person/create', name: USER.name, user_id: user.user.id }));
    }
    if (!byName.has(NO_USER.name)) {
      byName.set(NO_USER.name, await ws.call<PersonRow>({ type: 'person/create', name: NO_USER.name }));
    }
    // The seed rooms link to the areas `living_room` (onboarding makes it) and `office`.
    const areas = await ws.call<Array<{ area_id: string }>>({ type: 'config/area_registry/list' });
    if (!areas.some((a) => a.area_id === 'office')) {
      await ws.call({ type: 'config/area_registry/create', name: 'Office' });
    }
    for (const want of [ADMIN, USER, NO_USER]) {
      const got = byName.get(want.name)?.id;
      if (got !== want.person) throw new Error(`person ${want.name} has the id ${got}, and the seed needs ${want.person}`);
    }
  } finally {
    ws.close();
  }
}

/** Wait until get_state answers, so the first spec does not meet a loading library. */
async function waitForLibrary(token: string, timeoutMs = 120_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let last = '';
  while (Date.now() < deadline) {
    const ws = await haWs(token);
    try {
      const state = await ws.call<{ books: unknown[]; home_keeper: { tab: boolean } }>({ type: 'home_keeper_library/get_state' });
      if (state.books.length && state.home_keeper.tab) return;
      last = `books ${state.books.length}, tab ${state.home_keeper.tab}`;
    } catch (err) {
      last = String((err as Error).message ?? err);
    } finally {
      ws.close();
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`the library did not load: ${last}`);
}

function storageState(tokens: Tokens): object {
  const hassTokens = {
    access_token: tokens.access_token,
    token_type: 'Bearer',
    refresh_token: tokens.refresh_token,
    expires_in: tokens.expires_in,
    hassUrl: HA_URL,
    clientId: CLIENT_ID,
    expires: Date.now() + tokens.expires_in * 1000,
  };
  return {
    cookies: [],
    origins: [
      {
        origin: HA_URL,
        localStorage: [
          { name: 'hassTokens', value: JSON.stringify(hassTokens) },
          { name: 'selectedLanguage', value: '"en"' },
        ],
      },
    ],
  };
}

export default async function globalSetup(): Promise<void> {
  await waitForHA();
  const admin = await onboardAdmin();
  await ensurePeople(admin.access_token);
  await waitForLibrary(admin.access_token);
  const user = await login(USER.username, USER.password);
  mkdirSync(AUTH_DIR, { recursive: true });
  writeFileSync(resolve(AUTH_DIR, 'state.json'), JSON.stringify(storageState(admin), null, 2));
  writeFileSync(resolve(AUTH_DIR, 'sam.json'), JSON.stringify(storageState(user), null, 2));
  writeFileSync(resolve(AUTH_DIR, 'token.json'), JSON.stringify({ admin: admin.refresh_token, user: user.refresh_token }));
}
