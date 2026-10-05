// The entry point of `library-tab.js`, the ES module that the Home Keeper panel
// imports for the Library tab.
import { HomeKeeperLibraryTab } from './tab';

export const TAB_TAG = 'home-keeper-library-tab';

if (!customElements.get(TAB_TAG)) {
  customElements.define(TAB_TAG, HomeKeeperLibraryTab);
}

export { HomeKeeperLibraryTab };
