import { HomeKeeperLibraryPanel } from './panel';

if (!customElements.get('home-keeper-library-panel')) {
  customElements.define('home-keeper-library-panel', HomeKeeperLibraryPanel);
}

export { HomeKeeperLibraryPanel };
