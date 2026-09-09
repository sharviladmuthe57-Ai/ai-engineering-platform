import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// In-memory test double only. Production writes exclusively to Google Sheets.
export function createScriptRuntime({ secret = 'test-secret-not-a-credential-000000000000', failWrite = false, failFlush = false, lockAvailable = true } = {}) {
  const rows = [];
  const properties = { WEBHOOK_SECRET: secret, SPREADSHEET_ID: 'test-sheet' };
  let released = 0;
  const sheet = {
    getLastRow: () => rows.length,
    appendRow(row) { if (failWrite && rows.length) throw new Error('Write failed'); rows.push(Array.from(row)); },
    setFrozenRows() {},
    getRange(row, col, count = 1, columns = 1) {
      return {
        getValues: () => rows.slice(row - 1, row - 1 + count).map(r => r.slice(col - 1, col - 1 + columns)),
        setFontWeight() {},
        createTextFinder(value) {
          return {
            matchEntireCell() { return this; }, useRegularExpression() { return this; },
            findNext: () => rows.slice(row - 1, row - 1 + count).some(r => r[col - 1] === value) ? {} : null,
          };
        },
      };
    },
  };
  const book = { getId: () => 'test-sheet', getSheetByName: () => sheet };
  const context = vm.createContext({
    Date,
    SpreadsheetApp: {
      getActiveSpreadsheet: () => book, openById: () => book,
      flush() { if (failFlush) { failFlush = false; throw new Error('Receipt lost'); } },
    },
    PropertiesService: { getScriptProperties: () => ({ getProperty: key => properties[key], setProperty: (key, value) => { properties[key] = value; } }) },
    LockService: { getScriptLock: () => ({ tryLock: () => lockAvailable, releaseLock: () => { released++; } }) },
    ContentService: { MimeType: { JSON: 'application/json' }, createTextOutput: text => ({ text, setMimeType() { return this; } }) },
  });
  vm.runInContext(readFileSync(new URL('../../scripts/google-apps-script.gs', import.meta.url), 'utf8'), context);
  context.setup();
  return {
    rows, secret, context, released: () => released,
    post: body => JSON.parse(context.doPost({ postData: { contents: typeof body === 'string' ? body : JSON.stringify(body) } }).text),
  };
}
