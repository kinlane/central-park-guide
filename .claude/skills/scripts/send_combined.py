#!/usr/bin/env python3
"""Send ONE combined Central Park Guide email to a single subscriber.

The per-persona sender (send_updates.py) sends N messages to a subscriber who
picked N personas. This sends the single assembled edition at
_emails/<week>/combined.md instead.

Recipients are never inferred — you must name one with --to, and it must match a
verified subscriber in s3://centralpark-guide/updates/. There is no "send to
everyone" mode here on purpose; this is the format under test.

Usage:
  python3 send_combined.py <YYYY-MM-DD> --to kinlane@gmail.com --dry-run
  python3 send_combined.py <YYYY-MM-DD> --to kinlane@gmail.com

Required env vars (read from repo .env one level up):
  FASTMAIL_CENTRAL_PARK_GUIDE_KEY  Fastmail SMTP app password
  AWS_KEY / AWS_SECRET             IAM creds with s3:Get/ListObject on the bucket
"""
import argparse, os, re, ssl, smtplib, sys, yaml, boto3, markdown
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ap = argparse.ArgumentParser()
ap.add_argument('week')
ap.add_argument('--to', required=True, help='exact email of a verified subscriber')
ap.add_argument('--dry-run', action='store_true')
ap.add_argument('--file', default='combined.md')
a = ap.parse_args()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
ENV_FILE = os.path.normpath(os.path.join(REPO_ROOT, '..', '.env'))
EMAIL_PATH = os.path.join(REPO_ROOT, '_emails', a.week, a.file)
LOG_DIR = os.path.join(REPO_ROOT, 'email', a.week)
LOG_PATH = os.path.join(LOG_DIR, 'send-log.yml')

if not os.path.exists(EMAIL_PATH):
    sys.exit(f"No email at {EMAIL_PATH}")

env = {}
for line in open(ENV_FILE):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

raw = open(EMAIL_PATH, encoding='utf-8').read()
m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
if not m:
    sys.exit("Could not parse frontmatter")
fm = yaml.safe_load(m.group(1))
body_md = m.group(2).strip()
subject = fm.get("subject", "Central Park Guide")

# Confirm the recipient is a verified subscriber before composing anything.
s3 = boto3.client("s3", aws_access_key_id=env["AWS_KEY"],
                  aws_secret_access_key=env["AWS_SECRET"], region_name="us-east-1")
resp = s3.list_objects_v2(Bucket="centralpark-guide", Prefix="updates/")
sub = None
for obj in resp.get("Contents", []):
    if not obj["Key"].endswith(".yml"):
        continue
    rec = yaml.safe_load(s3.get_object(Bucket="centralpark-guide",
                                       Key=obj["Key"])["Body"].read().decode())
    if rec.get("verified") and rec.get("email", "").lower() == a.to.lower():
        sub = rec
        break
if not sub:
    sys.exit(f"{a.to} is not a verified subscriber — refusing to send.")

covered = set(fm.get('personas') or [])
theirs = set(sub.get('personas') or [])
missing = theirs - covered
extra = covered - theirs
print(f"Recipient : {sub['name']} <{sub['email']}>")
print(f"Subject   : {subject}")
print(f"Their personas ({len(theirs)}): {sorted(theirs)}")
if missing:
    print(f"!! email does NOT cover: {sorted(missing)}")
if extra:
    print(f"note: email covers personas they did not pick: {sorted(extra)}")
print(f"Body      : {len(body_md.splitlines())} lines, {len(body_md)} chars")

html_body = markdown.markdown(body_md, extensions=["tables", "extra"])
html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f3ee;font-family:Georgia,serif;color:#222;">
<div style="max-width:600px;margin:0 auto;background:#fff;padding:32px 24px;line-height:1.55;">
{html_body}
<hr style="border:none;border-top:1px solid #ddd;margin:32px 0 16px 0;">
<p style="font-size:12px;color:#888;">Central Park Guide &middot; hello@centralpark.guide<br>You signed up at <a href="https://centralpark.guide/updates/">centralpark.guide/updates/</a> &middot; <a href="https://centralpark.guide/updates/archive/">Archive</a></p>
</div></body></html>"""

if a.dry_run:
    print("\n--- DRY RUN, nothing sent ---")
    print(body_md[:1500])
    sys.exit(0)

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"] = "Central Park Guide <hello@centralpark.guide>"
msg["To"] = f"{sub['name']} <{sub['email']}>"
msg.attach(MIMEText(body_md, "plain", "utf-8"))
msg.attach(MIMEText(html_doc, "html", "utf-8"))

ctx = ssl.create_default_context()
print("\nConnecting to smtp.fastmail.com:587 ...")
with smtplib.SMTP("smtp.fastmail.com", 587, timeout=30) as s:
    s.ehlo(); s.starttls(context=ctx); s.ehlo()
    s.login("hello@centralpark.guide", env["FASTMAIL_CENTRAL_PARK_GUIDE_KEY"])
    refused = s.send_message(msg)
status = "refused" if refused else "sent"
print(f"  -> {status}")

os.makedirs(LOG_DIR, exist_ok=True)
log = []
if os.path.exists(LOG_PATH):
    log = yaml.safe_load(open(LOG_PATH)) or []
log.append({
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "to_name": sub["name"], "to_email": sub["email"],
    "format": "combined", "personas": sorted(theirs),
    "subject": subject, "week_of": a.week, "status": status,
})
yaml.safe_dump(log, open(LOG_PATH, "w"), sort_keys=False, default_flow_style=False)
print(f"Logged to {LOG_PATH}")
