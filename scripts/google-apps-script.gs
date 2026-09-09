// Paste this entire file into the Apps Script project attached to Kairo Labs Leads.
// Run setup() once as the owner, then deploy as a Web app (execute as Me, access Anyone).
// No credentials belong in this file. See docs/google-sheets-form-setup.md.
var LEAD_HEADERS = [
  'Timestamp', 'Name', 'Work Email', 'Company', 'Role', 'Company Type',
  'Current Workflow', 'Biggest Time Sink', 'First-Draft Electrical Usefulness',
  'Biggest Blocker', 'Open to 15-Minute Conversation', 'Phone / WhatsApp',
  'Source Page', 'Submission ID'
];
var LEAD_TAB = 'Responses';

function setup() {
  var book = SpreadsheetApp.getActiveSpreadsheet();
  if (!book) throw new Error('Open Extensions > Apps Script from Kairo Labs Leads first.');
  var properties = PropertiesService.getScriptProperties();
  properties.setProperty('SPREADSHEET_ID', book.getId());
  if (!properties.getProperty('WEBHOOK_SECRET')) {
    properties.setProperty('WEBHOOK_SECRET', Utilities.getUuid() + Utilities.getUuid());
  }
  var sheet = book.getSheetByName(LEAD_TAB) || book.insertSheet(LEAD_TAB);
  if (sheet.getLastRow() === 0) sheet.appendRow(LEAD_HEADERS);
  checkHeaders_(sheet);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, LEAD_HEADERS.length).setFontWeight('bold');
  // View WEBHOOK_SECRET in Project Settings > Script properties, not execution logs.
}

function doPost(event) {
  var lock;
  var locked = false;
  try {
    if (!event || !event.postData || event.postData.contents.length > 24000) return json_({ ok: false });
    var body = JSON.parse(event.postData.contents);
    var properties = PropertiesService.getScriptProperties();
    var secret = properties.getProperty('WEBHOOK_SECRET');
    if (!secret || secret.length < 32 || body.secret !== secret) return json_({ ok: false });
    if (typeof body.submissionId !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(body.submissionId)) return json_({ ok: false });
    var fields = validateFields_(body.fields);
    if (!fields) return json_({ ok: false });

    lock = LockService.getScriptLock();
    locked = lock.tryLock(10000);
    if (!locked) return json_({ ok: false });
    var book = SpreadsheetApp.openById(properties.getProperty('SPREADSHEET_ID'));
    var sheet = book.getSheetByName(LEAD_TAB);
    if (!sheet) return json_({ ok: false });
    checkHeaders_(sheet);
    var lastRow = sheet.getLastRow();
    // Durable retry protection: checking and writing happen under the same script lock.
    if (lastRow > 1 && sheet.getRange(2, 14, lastRow - 1, 1).createTextFinder(body.submissionId).matchEntireCell(true).useRegularExpression(false).findNext()) {
      return json_({ ok: true, submissionId: body.submissionId });
    }
    var values = [fields.name, fields.email, fields.company, fields.role, fields.company_type,
      fields.current_process, fields.time_sink, fields.usefulness, fields.barriers,
      fields.conversation, fields.phone, '/#feedback', body.submissionId];
    sheet.appendRow([new Date()].concat(values.map(safeCell_)));
    SpreadsheetApp.flush();
    return json_({ ok: true, submissionId: body.submissionId });
  } catch (error) {
    // Fail closed; never return or log response contents, account details, or secrets.
    return json_({ ok: false });
  } finally {
    if (locked) lock.releaseLock();
  }
}

function validateFields_(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
  var limits = { name: 120, email: 254, company: 160, role: 120, company_type: 80,
    phone: 50, current_process: 2000, time_sink: 2000, usefulness: 40, barriers: 2000, conversation: 3 };
  var fields = {};
  var keys = Object.keys(limits);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    if (typeof input[key] !== 'string') return null;
    var value = input[key].trim();
    if (value.length > limits[key] || (key !== 'phone' && !value)) return null;
    if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)) return null;
    fields[key] = value;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) return null;
  if (['Electrical Contractor', 'MEP Consultancy', 'Engineering Consultancy', 'Construction Company', 'Architecture Firm', 'BIM Team', 'Building Automation', 'Other'].indexOf(fields.company_type) < 0) return null;
  if (['Very useful', 'Possibly useful', 'Depends', 'Not useful'].indexOf(fields.usefulness) < 0) return null;
  if (['Yes', 'No'].indexOf(fields.conversation) < 0) return null;
  return fields;
}

function safeCell_(value) {
  // Treat visitor text as text, including when exported to Excel. Never execute formulas.
  return /^[=+@-]/.test(value) ? "'" + value : value;
}

function checkHeaders_(sheet) {
  var headers = sheet.getRange(1, 1, 1, LEAD_HEADERS.length).getValues()[0];
  if (headers.join('\t') !== LEAD_HEADERS.join('\t')) throw new Error('Unexpected column order.');
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  return json_({ ok: false, message: 'Submit through the website form. This endpoint does not expose leads.' });
}
