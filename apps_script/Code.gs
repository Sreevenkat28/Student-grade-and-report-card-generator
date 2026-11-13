/**
 * Grade & Report Card Generator - email sender (Google Apps Script)
 *
 * Sends the 6-digit confirmation codes FROM YOUR OWN Gmail account.
 * The Streamlit app calls this script; the script is the only thing that touches Gmail.
 *
 * SETUP (once):
 *  1. Project Settings (gear icon) -> Script properties -> Add property:
 *       Name: SECRET     Value: a long random string you make up (30+ characters)
 *  2. Run the function  authorize  once (Run button) and approve the Gmail permission.
 *  3. Deploy -> New deployment -> type "Web app":
 *       Execute as: Me        Who has access: Anyone
 *     Click Deploy and copy the Web app URL (ends in /exec).
 *  4. In Streamlit -> Settings -> Secrets add:
 *       [apps_script]
 *       url = "<the /exec URL>"
 *       token = "<the same SECRET value>"
 *
 * SAFETY: requests without the right SECRET are refused, and the script can only send the
 * fixed "confirmation code" / "test" emails (never custom text), at most 30 per address per hour.
 */

var MAX_PER_HOUR = 30;
var APP_NAME = 'Grade & Report Card Generator';
var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    var secret = PropertiesService.getScriptProperties().getProperty('SECRET');
    if (!secret || data.token !== secret) return reply_({ ok: false, error: 'unauthorized' });

    var to = String(data.to || '').trim().toLowerCase();
    if (to.length > 254 || !EMAIL_RE.test(to)) return reply_({ ok: false, error: 'bad_email' });

    var subject, body;
    if (data.kind === 'code') {
      var code = String(data.code || '');
      if (!/^\d{6}$/.test(code)) return reply_({ ok: false, error: 'bad_code' });
      subject = 'Your confirmation code: ' + code;
      body = 'Your ' + APP_NAME + ' confirmation code is ' + code + '.\n\n' +
             'Enter it in the app to continue. It expires in 10 minutes.\n' +
             'If you did not ask for this, you can ignore this email.';
    } else if (data.kind === 'test') {
      subject = 'Test email from ' + APP_NAME;
      body = 'This is a test. Email sending from the app is working, so confirmation codes will arrive.';
    } else {
      return reply_({ ok: false, error: 'bad_kind' });
    }

    // Per-recipient hourly limit so the endpoint can't be used to spam someone.
    var cache = CacheService.getScriptCache();
    var key = 'rl_' + Utilities.base64EncodeWebSafe(
        Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, to));
    var sent = Number(cache.get(key) || 0);
    if (sent >= MAX_PER_HOUR) return reply_({ ok: false, error: 'rate_limited' });
    cache.put(key, String(sent + 1), 3600);

    MailApp.sendEmail({ to: to, subject: subject, body: body, name: APP_NAME });
    return reply_({ ok: true });
  } catch (err) {
    return reply_({ ok: false, error: 'server_error' });
  }
}

// Opening the URL in a browser shows this, which is a handy "is it deployed?" check.
function doGet() {
  return reply_({ ok: true, service: 'grade-mailer' });
}

// Run this once from the editor so Google asks you to grant permission to send mail.
function authorize() {
  Logger.log('Emails left today: ' + MailApp.getRemainingDailyQuota());
}

function reply_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
      .setMimeType(ContentService.MimeType.JSON);
}
