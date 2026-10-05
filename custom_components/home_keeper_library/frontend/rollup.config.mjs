import json from '@rollup/plugin-json';
import { nodeResolve } from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';
import typescript from '@rollup/plugin-typescript';
import virtual from '@rollup/plugin-virtual';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// PANEL_VERSION in const.py is the source of the version (release.yml checks that it
// is the same as the manifest.json version). Both bundles show it.
const constPy = resolve(dirname(fileURLToPath(import.meta.url)), '../const.py');
let PANEL_VERSION = '0.0.0';
try {
  const match = readFileSync(constPy, 'utf8').match(/PANEL_VERSION\s*=\s*"([^"]+)"/);
  if (match) PANEL_VERSION = match[1];
  else console.warn('Warning: PANEL_VERSION not found in const.py, using 0.0.0');
} catch (err) {
  throw new Error(`Failed to read version from const.py: ${err.message}`);
}

const BUILD_DATE = new Date().toISOString().split('T')[0];

// Each bundle has its locale JSON and the version string. `nodeResolve` is only for
// @zxing/library, which goes into the lazy decoder chunk of the tab.
const plugins = () => [
  json({ compact: true }),
  nodeResolve({ browser: true }),
  typescript({ tsconfig: './tsconfig.json' }),
  virtual({ 'panel-version': `export const PANEL_VERSION = '${PANEL_VERSION}';` }),
  terser({ format: { comments: /^\**\n \* Home Keeper Library/ } }),
];

// zxing is compiled TypeScript with `this` at the top level of each module. In an ES
// module that `this` is undefined, which the zxing code expects, so the warning is noise.
const onwarn = (warning, warn) => {
  if (warning.code === 'THIS_IS_UNDEFINED' && /@zxing/.test(warning.id ?? '')) return;
  warn(warning);
};

const banner = (what) =>
  `/**\n * Home Keeper Library ${what}.\n * Version: ${PANEL_VERSION}\n * Built: ${BUILD_DATE}\n */`;

// The output is `dist/` only. The integration serves `dist/` as a static path, so
// the sources, the tests and node_modules are not public. Both bundles are ES
// modules. The tab bundle has 1 chunk: the zxing decoder, which loads only when
// the scanner opens on a browser with no native BarcodeDetector.
export default [
  {
    input: { 'library-tab': 'src/tab-index.ts' },
    output: {
      dir: 'dist',
      format: 'es',
      entryFileNames: '[name].js',
      chunkFileNames: 'chunks/[name]-[hash].js',
      banner: banner('tab (Home Keeper panel tab module)'),
    },
    plugins: plugins(),
    onwarn,
  },
  {
    input: { 'library-card': 'src/card-index.ts' },
    output: {
      dir: 'dist',
      format: 'es',
      entryFileNames: '[name].js',
      inlineDynamicImports: true,
      banner: banner('card (Lovelace card)'),
    },
    plugins: plugins(),
    onwarn,
  },
];
