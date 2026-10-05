// The entry point of `library-card.js`, the Lovelace resource of the card.
import { CARD_TAG, EDITOR_TAG, HomeKeeperLibraryCard, HomeKeeperLibraryCardEditor } from './card';
import { t } from './i18n';

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, HomeKeeperLibraryCard);
if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, HomeKeeperLibraryCardEditor);

interface CustomCard {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}

// Add the card to the dashboard card picker.
const w = window as unknown as { customCards?: CustomCard[] };
w.customCards = w.customCards || [];
if (!w.customCards.some((c) => c.type === CARD_TAG)) {
  w.customCards.push({
    type: CARD_TAG,
    name: t('card.name'),
    description: t('card.description'),
    preview: true,
    documentationURL: 'https://github.com/prestomation/ha-home-keeper-library',
  });
}

export { HomeKeeperLibraryCard, HomeKeeperLibraryCardEditor };
