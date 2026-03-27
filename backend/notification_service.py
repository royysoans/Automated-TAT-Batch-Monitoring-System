import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFICATION_FROM = os.environ.get("NOTIFICATION_FROM", "tat-monitor@lab.local")
NOTIFICATION_TO = os.environ.get("NOTIFICATION_TO", "")

NOTIFICATIONS_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and NOTIFICATION_TO)

SEVERITY_COLORS = {
    "critical": "#DC2626",
    "warning": "#F59E0B",
    "info": "#3B82F6",
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "⚠️",
    "info": "ℹ️",
}

def build_email_html(alert_type, severity, message, sample_id, test_code):
    color = SEVERITY_COLORS.get(severity, "#6B7280")
    emoji = SEVERITY_EMOJI.get(severity, "📋")
    alert_label = alert_type.replace("_", " ").upper()

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #0F172A; color: white; padding: 20px 24px; border-radius: 12px 12px 0 0;">
            <h2 style="margin: 0; font-size: 18px;">🔬 TAT Monitor Alert</h2>
            <p style="margin: 4px 0 0; opacity: 0.7; font-size: 13px;">Automated Laboratory Monitoring System</p>
        </div>
        <div style="border: 1px solid #E2E8F0; border-top: none; padding: 24px; border-radius: 0 0 12px 12px;">
            <div style="display: inline-block; background: {color}20; color: {color}; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 16px;">
                {emoji} {alert_label} — {severity.upper()}
            </div>
            <p style="font-size: 15px; color: #1E293B; line-height: 1.6; margin: 12px 0;">{message}</p>
            <div style="background: #F8FAFC; border-radius: 8px; padding: 16px; margin-top: 16px;">
                <table style="width: 100%; font-size: 13px; color: #475569;">
                    <tr><td style="padding: 4px 0; font-weight: 600; width: 30%;">Sample ID</td><td style="font-family: monospace; color: #0F172A;">{sample_id}</td></tr>
                    <tr><td style="padding: 4px 0; font-weight: 600;">Test Code</td><td style="font-family: monospace; color: #0F172A;">{test_code}</td></tr>
                    <tr><td style="padding: 4px 0; font-weight: 600;">Severity</td><td><span style="color: {color}; font-weight: 600;">{severity.upper()}</span></td></tr>
                </table>
            </div>
            <p style="font-size: 12px; color: #94A3B8; margin-top: 20px; border-top: 1px solid #E2E8F0; padding-top: 16px;">
                This is an automated notification from the TAT & Batch Monitoring System.
                Please log in to the dashboard to acknowledge and manage this alert.
            </p>
        </div>
    </div>
    """

def send_email_notification(alert_type, severity, message, sample_id, test_code, user_email=None, subject_override=None):
    if not NOTIFICATIONS_ENABLED:
        return {"sent": False, "reason": "Email notifications not configured (missing SMTP env vars)"}

    try:
        if user_email:
            recipients = [user_email]
        else:
            recipients = [r.strip() for r in NOTIFICATION_TO.split(",") if r.strip()]
            
        if not recipients:
            return {"sent": False, "reason": "No recipients configured"}

        emoji = SEVERITY_EMOJI.get(severity, "📋")
        alert_label = alert_type.replace("_", " ").upper()
        subject = subject_override if subject_override else f"{emoji} [{severity.upper()}] {alert_label} — Sample {sample_id}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = NOTIFICATION_FROM
        msg["To"] = ", ".join(recipients)

        plain_text = f"""
TAT Monitor Alert
==================
Type: {alert_label}
Severity: {severity.upper()}
Sample: {sample_id}
Test: {test_code}

{message}

— TAT & Batch Monitoring System
        """.strip()

        html_content = build_email_html(alert_type, severity, message, sample_id, test_code)

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(NOTIFICATION_FROM, recipients, msg.as_string())

        return {"sent": True, "recipients": recipients}

    except Exception as e:
        print(f"[NOTIFICATION ERROR] Failed to send email: {e}")
        return {"sent": False, "reason": str(e)}


def send_alert_notification(alert_type, severity, message, sample_id, test_code, user_email=None):
    results = {}
    email_result = send_email_notification(alert_type, severity, message, sample_id, test_code, user_email=user_email)
    results["email"] = email_result
    return results

def send_confirmation_email(sample_id, test_code, received_at, batch_cutoff, eta, user_email):
    message = (
        f"Your sample has been accessioned successfully.<br><br>"
        f"<b>Received:</b> {received_at.strftime('%A, %b %d at %I:%M %p')}<br>"
        f"<b>Batch Assignment:</b> {batch_cutoff.strftime('%A, %b %d at %I:%M %p')}<br>"
        f"<b>Expected Result (ETA):</b> <span style='font-size: 16px; font-weight: 700; color: #2563EB;'>{eta.strftime('%A, %b %d at %I:%M %p')}</span>"
    )
    return send_email_notification(
        "intake_confirmation", "info", message, sample_id, test_code, 
        user_email=user_email, 
        subject_override=f"✅ Sample Intake Confirmed — ETA: {eta.strftime('%I:%M %p')}"
    )

def send_completion_email(sample_id, test_code, user_email):
    message = f"Processing is complete for sample <b>{sample_id}</b>. The results are now available."
    return send_email_notification(
        "sample_completed", "info", message, sample_id, test_code, 
        user_email=user_email, 
        subject_override=f"🎉 Sample Completed — {sample_id}"
    )
