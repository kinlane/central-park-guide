#!/usr/bin/env python3
"""Official Central Park Guide updates send.

Pulls verified subscribers from s3://centralpark-guide/updates/, picks the email
for each (subscriber × persona) from _emails/<week>/<persona>.md, sends via
Fastmail SMTP, and appends per-send results to a YAML log.

Usage:
  python3 .claude/skills/scripts/send_updates.py <YYYY-MM-DD>

Where <YYYY-MM-DD> is the week_of date that matches the _emails/<week>/ folder.

Required env vars (read from repo .env one level up):
  FASTMAIL_CENTRAL_PARK_GUIDE_KEY  Fastmail SMTP app password
  AWS_KEY / AWS_SECRET             IAM creds with s3:Get/ListObject on the bucket

Log file:
  central-park-guide/email/<week>/send-log.yml
"""
import os, re, sys, ssl, time, smtplib, yaml, boto3, markdown
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

if len(sys.argv) < 2:
    sys.exit("usage: send_updates.py <YYYY-MM-DD>")

WEEK = sys.argv[1]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
ENV_FILE = os.path.normpath(os.path.join(REPO_ROOT, '..', '.env'))
EMAILS_DIR = os.path.join(REPO_ROOT, '_emails', WEEK)
LOG_DIR = os.path.join(REPO_ROOT, 'email', WEEK)
LOG_PATH = os.path.join(LOG_DIR, 'send-log.yml')

BUCKET = "centralpark-guide"
PREFIX = "updates/"

if not os.path.isdir(EMAILS_DIR):
    sys.exit(f"No emails folder at {EMAILS_DIR}")
os.makedirs(LOG_DIR, exist_ok=True)

env = {}
with open(ENV_FILE) as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

smtp_password = env["FASTMAIL_CENTRAL_PARK_GUIDE_KEY"]

s3 = boto3.client(
    "s3",
    aws_access_key_id=env["AWS_KEY"],
    aws_secret_access_key=env["AWS_SECRET"],
    region_name="us-east-1",
)
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)
subscribers = []
for obj in resp.get("Contents", []):
    if not obj["Key"].endswith(".yml"):
        continue
    body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode()
    rec = yaml.safe_load(body)
    if rec.get("verified"):
        subscribers.append(rec)
print(f"Loaded {len(subscribers)} verified subscriber(s) from s3://{BUCKET}/{PREFIX}")
for sub in subscribers:
    print(f"  - {sub['name']} <{sub['email']}>: {sub.get('personas', [])}")


def build_message(persona, to_name, to_email):
    path = os.path.join(EMAILS_DIR, f"{persona}.md")
    if not os.path.exists(path):
        return None, None, f"Email file not found: {path}"
    with open(path) as f:
        raw = f.read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
    if not m:
        return None, None, "Could not parse frontmatter"
    fm = yaml.safe_load(m.group(1))
    body_md = m.group(2).strip()
    subject = fm.get("subject", "Central Park Guide")
    html_body = markdown.markdown(body_md, extensions=["tables", "extra"])
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f3ee;font-family:Georgia,serif;color:#222;">
<div style="max-width:600px;margin:0 auto;background:#fff;padding:32px 24px;line-height:1.55;">
{html_body}
<hr style="border:none;border-top:1px solid #ddd;margin:32px 0 16px 0;">
<p style="font-size:12px;color:#888;">Central Park Guide &middot; hello@centralpark.guide<br>You signed up at <a href="https://centralpark.guide/updates/">centralpark.guide/updates/</a> &middot; <a href="https://centralpark.guide/updates/archive/">Archive</a></p>
</div></body></html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = "Central Park Guide <hello@centralpark.guide>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg.attach(MIMEText(body_md, "plain", "utf-8"))
    msg.attach(MIMEText(html_doc, "html", "utf-8"))
    return msg, subject, None


log_entries = []
ctx = ssl.create_default_context()
print("\nConnecting to smtp.fastmail.com:587 ...")
with smtplib.SMTP("smtp.fastmail.com", 587, timeout=30) as s:
    s.ehlo(); s.starttls(context=ctx); s.ehlo()
    s.login("hello@centralpark.guide", smtp_password)
    for sub in subscribers:
        name, email_addr = sub["name"], sub["email"]
        for persona in sub.get("personas", []):
            msg, subject, err = build_message(persona, name, email_addr)
            ts = datetime.now(timezone.utc).isoformat()
            entry = {
                "timestamp": ts,
                "to_name": name,
                "to_email": email_addr,
                "persona": persona,
                "subject": subject,
                "week_of": WEEK,
            }
            if err:
                entry["status"] = "error"
                entry["error"] = err
                print(f"  {name:18s} {persona:18s} -> ERROR: {err}")
            else:
                try:
                    refused = s.send_message(msg)
                    if refused:
                        entry["status"] = "refused"
                        entry["refused"] = refused
                        print(f"  {name:18s} {persona:18s} -> REFUSED: {refused}")
                    else:
                        entry["status"] = "sent"
                        print(f"  {name:18s} {persona:18s} -> sent")
                except Exception as e:
                    entry["status"] = "error"
                    entry["error"] = str(e)
                    print(f"  {name:18s} {persona:18s} -> ERROR: {e}")
            log_entries.append(entry)
            time.sleep(0.4)

existing_log = []
if os.path.exists(LOG_PATH):
    with open(LOG_PATH) as f:
        existing_log = yaml.safe_load(f) or []
combined = existing_log + log_entries
with open(LOG_PATH, "w") as f:
    yaml.safe_dump(combined, f, sort_keys=False, default_flow_style=False)

sent = sum(1 for e in log_entries if e["status"] == "sent")
print(f"\nDone. {sent}/{len(log_entries)} sent. Log: {LOG_PATH}")
