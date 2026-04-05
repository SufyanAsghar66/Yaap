"""
Email Service
Sends transactional emails (OTP codes, password reset links).
Uses Supabase's built-in email provider for simplicity.
Can be swapped for SendGrid/SES by changing the send implementation.
"""

import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Core send function. In production wire this to:
      - AWS SES (boto3 ses client)
      - SendGrid (sendgrid.SendGridAPIClient)
      - Supabase email (via supabase.auth.admin.invite_user_by_email for invites)
    For now uses Python's smtplib via Django's email backend.
    """
    from django.core.mail import send_mail
    try:
        send_mail(
            subject         = subject,
            message         = "",          # plain text fallback
            html_message    = html_body,
            from_email      = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@yaap.app"),
            recipient_list  = [to],
            fail_silently   = False,
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False


# ─── OTP Email ────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=10, name="email.send_otp")
def send_otp_email(self, email: str, code: str):
    """
    Celery task — sends a 6-digit OTP to the user's email.
    Retries up to 3 times on failure with 10s delay.
    """
    subject = "Your YAAP login code"
    html    = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
      <h2 style="color: #2563EB; margin-bottom: 8px;">YAAP</h2>
      <p style="color: #374151; font-size: 16px;">
        Your one-time login code is:
      </p>
      <div style="
        background: #EFF6FF;
        border: 2px solid #2563EB;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin: 24px 0;
      ">
        <span style="
          font-size: 48px;
          font-weight: 800;
          letter-spacing: 12px;
          color: #1E3A5F;
          font-family: monospace;
        ">{code}</span>
      </div>
      <p style="color: #6B7280; font-size: 14px;">
        This code expires in <strong>{settings.OTP_EXPIRY_MINUTES} minutes</strong>.
        If you didn't request this, you can safely ignore this email.
      </p>
      <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 24px 0;" />
      <p style="color: #9CA3AF; font-size: 12px;">YAAP — Real-time voice calls, any language.</p>
    </div>
    """
    try:
        _send_email(email, subject, html)
    except Exception as exc:
        logger.error("OTP email failed for %s, retrying. Error: %s", email, exc)
        raise self.retry(exc=exc)


# ─── Password Reset Email ─────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=10, name="email.send_password_reset")
def send_password_reset_email(self, email: str):
    """
    Triggers a password reset email via Supabase Auth.
    Supabase generates the secure reset token and hosts the link.
    """
    try:
        from services.supabase_client import get_supabase_admin_client
        supabase = get_supabase_admin_client()
        # Supabase sends the reset email natively with its own token
        supabase.auth.admin.generate_link({
            "type":       "recovery",
            "email":      email,
            "redirect_to": f"{settings.FRONTEND_URL}/reset-password",
        })
        logger.info("Password reset link generated for %s", email)
    except Exception as exc:
        logger.error("Password reset email failed for %s: %s", email, exc)
        raise self.retry(exc=exc)


# ─── Welcome Email ────────────────────────────────────────────────────────────

@shared_task(name="email.send_welcome")
def send_welcome_email(email: str, display_name: str):
    subject = f"Welcome to YAAP, {display_name}!"
    html    = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
      <h2 style="color: #2563EB;">Welcome to YAAP, {display_name}! 🎉</h2>
      <p style="color: #374151; font-size: 16px;">
        You're all set to start making voice calls across any language barrier.
      </p>
      <p style="color: #374151;">
        Next step: complete your profile and record 5 voice samples so we can
        clone your voice for real-time translation.
      </p>
      <p style="color: #9CA3AF; font-size: 12px; margin-top: 32px;">
        YAAP — Real-time voice calls, any language.
      </p>
    </div>
    """
    _send_email(email, subject, html)


@shared_task(name="email.cleanup_expired_otps")
def cleanup_expired_otps():
    """Periodic task: delete used and expired OTPs older than 24 hours."""
    from django.utils import timezone
    from datetime import timedelta
    from apps.accounts.models import EmailOTP
    cutoff  = timezone.now() - timedelta(hours=24)
    deleted, _ = EmailOTP.objects.filter(expires_at__lt=cutoff).delete()
    return {"deleted": deleted}
