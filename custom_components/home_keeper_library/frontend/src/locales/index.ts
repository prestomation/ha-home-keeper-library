// The locale tables. Rollup puts them in the bundle, so there is no fetch at run
// time. English is the source and the fallback. `test/i18n-parity.test.js` checks
// every other table against it.
import ca from './ca.json';
import cs from './cs.json';
import da from './da.json';
import de from './de.json';
import en from './en.json';
import es from './es.json';
import fi from './fi.json';
import fr from './fr.json';
import it from './it.json';
import nb from './nb.json';
import nl from './nl.json';
import pl from './pl.json';
import ptBR from './pt-BR.json';
import ru from './ru.json';
import sv from './sv.json';
import zhHans from './zh-Hans.json';

export const DEFAULT_LOCALE = 'en';

export const LOCALES: Record<string, Record<string, string>> = {
  ca,
  cs,
  da,
  de,
  en,
  es,
  fi,
  fr,
  it,
  nb,
  nl,
  pl,
  'pt-BR': ptBR,
  ru,
  sv,
  'zh-Hans': zhHans,
};
