// The state that the tab views read. The views are free functions over `ViewCtx`.

import type { ImportSummary, Lib, ScanResult } from './types';
import type { Index, TabRoute } from './utils';

export interface ScanEntry {
  key: number;
  isbn: string;
  pending: boolean;
  res: ScanResult | null;
  error?: string;
  /** What the user picked for a duplicate. */
  choice?: 'move' | 'add_copy' | 'skip';
}

export interface ScanSession {
  method: 'camera' | 'manual';
  roomId: string | null;
  results: ScanEntry[];
  manualOpen: boolean;
  markRead: boolean;
  cameraError: '' | 'insecure' | 'denied' | 'unsupported';
  torch: boolean | null;
  party: string;
  personId: string | null;
  due: string;
  addTask: boolean;
}

export interface ImportState {
  source: 'goodreads' | 'storygraph' | 'library';
  personId: string | null;
  shelfId: string;
  fileName: string;
  content: string;
  rowCount: number;
  importNotes: boolean;
  replaceReading: boolean;
  summary: ImportSummary | null;
  busy: boolean;
  error: string;
  done: boolean;
}

export interface UiState {
  limit: number;
  notesTab: 'shared' | 'private';
  editNotes: boolean;
  readingPerson: string | null;
  scan: ScanSession;
  import: ImportState;
  todoEntities: Array<{ entity_id: string; name?: string }>;
  exportFormat: 'goodreads' | 'library';
  exportPerson: string;
}

export interface ViewCtx {
  lib: Lib;
  idx: Index;
  route: TabRoute;
  me: string | null;
  today: string;
  ui: UiState;
  /** The book list path to go back to from a book. */
  booksPath: string;
  taskLink: (id: string) => string;
  areaName: (id: string) => string;
  todoName: (entityId: string) => string;
}
