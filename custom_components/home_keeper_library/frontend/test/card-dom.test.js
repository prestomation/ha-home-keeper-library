import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/card-index.ts';
import { sectionsOn } from '../src/card.ts';
import { ALEX, bookId, fakeHass, fixture, flush, SAM } from './fake-hass.js';

let el;

async function mount(config = {}, opts = {}) {
  const fake = fakeHass(opts);
  el = document.createElement('home-keeper-library-card');
  el.setConfig({ type: 'custom:home-keeper-library-card', ...config });
  document.body.appendChild(el);
  el.hass = fake.hass;
  await flush();
  return fake;
}

const $ = (sel) => el.shadowRoot.querySelector(sel);
const $$ = (sel) => [...el.shadowRoot.querySelectorAll(sel)];
const text = () => el.shadowRoot.textContent.replace(/\s+/g, ' ');

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 5, 12));
});
afterEach(() => {
  el?.remove();
  vi.useRealTimers();
});

describe('card', () => {
  it('registers in the card picker', () => {
    expect(window.customCards.some((c) => c.type === 'home-keeper-library-card')).toBe(true);
    expect(customElements.get('home-keeper-library-card').getStubConfig()).toEqual({ type: 'custom:home-keeper-library-card' });
  });

  it('shows the reading, want to read, goal and household of the caller', async () => {
    const fake = await mount();
    expect(fake.calls('get_state')).toHaveLength(1);
    expect($('h2').textContent).toBe('Library: Alex');
    expect(text()).toContain('36 books');
    expect(text()).toContain('Project Hail Mary');
    expect(text()).toContain('Page 210 of 476');
    expect(text()).toContain('Want to read · 2');
    expect(text()).toContain('6 of 24 books in 2026');
    expect(text()).toContain('Goal: 24 · 2,124 pages');
    expect(text()).toContain('Sam: reading The Left Hand of Darkness');
    expect(text()).toContain('2 days ago');
  });

  it('hides the household rows of a person who does not share', async () => {
    const state = fixture();
    state.people[SAM].share_reading = false;
    await mount({}, { state });
    expect(text()).not.toContain('Sam: reading');
    expect(text()).toContain('Jo: reading The Tombs of Atuan');
  });

  it('sets the page and the read status for the caller, with no person_id', async () => {
    const state = fixture();
    const id = bookId(state, 'Project Hail Mary');
    const fake = await mount();
    $(`[data-k="sp-${id}"]`).click();
    const input = $(`[data-k="page-${id}"]`);
    input.value = '250';
    input.form.requestSubmit();
    await flush();
    expect(fake.calls('set_reading')[0]).toEqual({ type: 'home_keeper_library/set_reading', book_id: id, page: 250 });
    $(`[data-k="rd-${id}"]`).click();
    await flush();
    expect(fake.calls('set_reading')[1]).toEqual({ type: 'home_keeper_library/set_reading', book_id: id, status: 'read', finished: '2026-10-05', read_count: 1 });
  });

  it('searches and adds a book to want to read', async () => {
    const state = fixture();
    const fake = await mount();
    const input = $('[data-k="q"]');
    input.focus();
    input.value = 'lavinia';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 200));
    expect(text()).toContain('Living room › Bookcase A › Shelf 3');
    expect(el.shadowRoot.activeElement?.dataset.k).toBe('q');
    $(`[data-k="w-${bookId(state, 'Lavinia')}"]`).click();
    await flush();
    expect(fake.calls('set_reading')[0]).toMatchObject({ book_id: bookId(state, 'Lavinia'), status: 'want' });
  });

  it('shows another person for an admin, with person_id in the call', async () => {
    const state = fixture();
    const fake = await mount({ person: SAM });
    expect($('h2').textContent).toBe('Library: Sam');
    const id = bookId(state, 'The Left Hand of Darkness');
    $(`[data-k="rd-${id}"]`).click();
    await flush();
    expect(fake.calls('set_reading')[0]).toMatchObject({ book_id: id, person_id: SAM, status: 'read' });
  });

  it('ignores the person option for a non-admin user', async () => {
    const state = fixture();
    state.me.is_admin = false;
    await mount({ person: SAM }, { state });
    expect($('h2').textContent).toBe('Library: Alex');
  });

  it('says so when no person is linked', async () => {
    const state = fixture();
    state.me.person_id = null;
    await mount({}, { state });
    expect(text()).toContain('No person is linked to this user.');
  });

  it('picks a random book to read', async () => {
    const rnd = vi.spyOn(Math, 'random').mockReturnValue(0.99);
    await mount();
    $('[data-k="random"]').click();
    expect(text()).toContain('Pick: The Tombs of Atuan');
    expect($$('.pick')).toHaveLength(1);
    rnd.mockRestore();
  });

  it('hides the sections that are off', async () => {
    await mount({ search: false, reading: false, want: false, household: false, title: 'Books' });
    expect($('h2').textContent).toBe('Books');
    expect($('[data-k="q"]')).toBeNull();
    expect(text()).not.toContain('Project Hail Mary');
    expect(text()).toContain('6 of 24 books in 2026');
    expect(text()).not.toContain('Household');
  });

  it('reads the section toggles', () => {
    expect(sectionsOn({ type: 'x' })).toEqual({ search: true, reading: true, want: true, goal: true, household: true });
    expect(sectionsOn({ type: 'x', goal: false }).goal).toBe(false);
  });
});

describe('card editor', () => {
  it('sends config-changed for a section and a person', () => {
    const ed = document.createElement('home-keeper-library-card-editor');
    ed.hass = fakeHass().hass;
    ed.setConfig({ type: 'custom:home-keeper-library-card' });
    document.body.appendChild(ed);
    const events = [];
    ed.addEventListener('config-changed', (e) => events.push(e.detail.config));
    const box = ed.querySelector('[data-key="goal"]');
    box.checked = false;
    box.dispatchEvent(new Event('change'));
    expect(events.at(-1)).toEqual({ type: 'custom:home-keeper-library-card', goal: false });
    const sel = ed.querySelector('[data-key="person"]');
    expect([...sel.options].map((o) => o.textContent)).toEqual(['Current user', 'Alex', 'Jo', 'Sam']);
    sel.value = ALEX;
    sel.dispatchEvent(new Event('change'));
    expect(events.at(-1)).toEqual({ type: 'custom:home-keeper-library-card', goal: false, person: ALEX });
    ed.remove();
  });
});
