import { CARD_DESCRIPTION, CARD_NAME, HomeKeeperLibraryCard, HomeKeeperLibraryCardEditor } from './card';

if (!customElements.get('home-keeper-library-card')) {
  customElements.define('home-keeper-library-card', HomeKeeperLibraryCard);
}
if (!customElements.get('home-keeper-library-card-editor')) {
  customElements.define('home-keeper-library-card-editor', HomeKeeperLibraryCardEditor);
}

// Advertise the card in the dashboard "Add card" picker.
interface CustomCard {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}
const w = window as unknown as { customCards?: CustomCard[] };
w.customCards = w.customCards || [];
if (!w.customCards.some((c) => c.type === 'home-keeper-library-card')) {
  w.customCards.push({
    type: 'home-keeper-library-card',
    name: CARD_NAME,
    description: CARD_DESCRIPTION,
    preview: true,
    documentationURL: 'https://github.com/prestomation/ha-home-keeper-library',
  });
}

export { HomeKeeperLibraryCard, HomeKeeperLibraryCardEditor };
