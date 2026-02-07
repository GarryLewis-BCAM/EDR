#!/usr/bin/env python3
"""
Free Alerting System - No paid services required
- macOS notifications (osascript)
- Email via SMTP (Gmail/iCloud)
- Optional: Email-to-SMS gateway
"""
import subprocess
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

logger = logging.getLogger(__name__)


class FreeAlerter:
    """Free alerting using macOS notifications and email"""
    
    def __init__(self, config: dict):
        self.config = config
        alert_config = config.get('alerting', {}).get('free_alerts', {})
        
        # macOS Notifications
        self.notifications_enabled = alert_config.get('notifications', {}).get('enabled', True)
        self.notification_sound = alert_config.get('notifications', {}).get('sound', 'Sosumi')
        
        # Email/SMS
        email_config = alert_config.get('email', {})
        self.email_enabled = email_config.get('enabled', False)
        self.smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = email_config.get('smtp_port', 587)
        self.smtp_username = email_config.get('username')
        self.smtp_password = email_config.get('password')
        self.from_email = email_config.get('from_email', self.smtp_username)
        self.to_emails = email_config.get('to_emails', [])
        self.sms_gateway = email_config.get('sms_gateway')  # e.g., "0400539919@sms.telstra.com"
        
        self.min_severity = alert_config.get('min_severity', 'high')
        
        logger.info(f"Free alerting initialized: notifications={self.notifications_enabled}, email={self.email_enabled}")
    
    def send_alert(self, title: str, message: str, severity: str = 'medium', sound: bool = True):
        """Send alert via available free channels"""
        
        # Check severity filter
        severity_levels = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        if severity_levels.get(severity, 0) < severity_levels.get(self.min_severity, 2):
            return
        
        # macOS Notification
        if self.notifications_enabled:
            try:
                self._send_macos_notification(title, message, sound)
            except Exception as e:
                logger.warning(f"macOS notification failed: {e}")
        
        # Email (including SMS gateway)
        if self.email_enabled and (self.to_emails or self.sms_gateway):
            try:
                self._send_email(title, message, severity)
            except Exception as e:
                logger.warning(f"Email alert failed: {e}")
    
    def _send_macos_notification(self, title: str, message: str, sound: bool = True):
        """Send native macOS notification"""
        sound_param = f'sound name "{self.notification_sound}"' if sound else ''
        
        # Escape quotes in title and message
        title = title.replace('"', '\\"')
        message = message.replace('"', '\\"')
        
        script = f'''
        display notification "{message}" with title "{title}" {sound_param}
        '''
        
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        logger.info(f"macOS notification sent: {title}")
    
    def _send_email(self, title: str, message: str, severity: str):
        """Send email alert (can include SMS via email-to-SMS gateway)"""
        if not self.smtp_username or not self.smtp_password:
            logger.warning("Email not configured (missing credentials)")
            return
        
        # Prepare recipients (email + SMS gateway)
        recipients = list(self.to_emails)
        if self.sms_gateway:
            recipients.append(self.sms_gateway)
        
        if not recipients:
            return
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"[{severity.upper()}] {title}"
        
        # Email body
        body = f"""
BCAM EDR Alert
==============

Severity: {severity.upper()}
Time: {self._get_timestamp()}

{message}

---
BCAM Hybrid EDR System
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send via SMTP
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.from_email, recipients, msg.as_string())
            
            logger.info(f"Email sent to {len(recipients)} recipient(s)")
            
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            raise
    
    def _get_timestamp(self):
        """Get formatted timestamp"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def test(self):
        """Send test alert"""
        self.send_alert(
            title="✅ BCAM EDR Test Alert",
            message="Free alerting system is working! (macOS notifications + Email)",
            severity="medium"
        )
        print("✅ Test alert sent via free channels")
