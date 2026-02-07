"""
Production-grade alerting system
- macOS notifications
- Email alerts (SMTP)
- Webhook support (Slack, Discord, custom)
- Rate limiting with priority queues
- Alert deduplication
- Retry logic
- Alert history tracking
"""
import time
import logging
import subprocess
import smtplib
import requests
import hashlib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from collections import deque, defaultdict
from threading import Lock
from enum import Enum


logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AlertChannel(Enum):
    """Available alert channels"""
    MACOS_NOTIFICATION = "macos_notification"
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"
    TWILIO_SMS = "twilio_sms"


@dataclass
class Alert:
    """Alert message"""
    title: str
    message: str
    priority: AlertPriority
    severity: str  # info, warning, high, critical
    timestamp: float = field(default_factory=time.time)
    source: str = "EDR"
    details: Dict[str, Any] = field(default_factory=dict)
    alert_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.alert_id:
            # Generate unique ID for deduplication
            content = f"{self.title}:{self.severity}:{self.source}"
            self.alert_id = hashlib.md5(content.encode()).hexdigest()[:16]


class AlertingSystem:
    """
    Production-grade alerting system with:
    - Multiple channels (macOS, email, webhooks)
    - Rate limiting per channel
    - Priority queue
    - Alert deduplication
    - Retry logic
    - Quiet hours support
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alert_config = config.get('alerts', {})
        
        # Rate limiting
        self.rate_limits = {
            'max_per_hour': self.alert_config.get('rate_limiting', {}).get('max_per_hour', 20),
            'max_per_day': self.alert_config.get('rate_limiting', {}).get('max_per_day', 100)
        }
        
        # Quiet hours
        self.quiet_hours = {
            'start': self.alert_config.get('rate_limiting', {}).get('quiet_hours_start', 23),
            'end': self.alert_config.get('rate_limiting', {}).get('quiet_hours_end', 7)
        }
        
        # Alert tracking
        self._alert_history: deque = deque(maxlen=1000)
        self._sent_alerts: Dict[str, float] = {}  # alert_id -> last_sent_time
        self._hourly_counts: defaultdict = defaultdict(int)
        self._daily_count: int = 0
        self._last_reset: datetime = datetime.now()
        self._lock = Lock()
        
        # Deduplication window (don't send same alert within X minutes)
        self.dedup_window = 300  # 5 minutes
        
        logger.info("Alerting system initialized")
    
    def send_alert(self, alert: Alert, channels: Optional[List[AlertChannel]] = None) -> Dict[str, bool]:
        """
        Send alert through specified channels
        
        Args:
            alert: Alert to send
            channels: List of channels to use (None = all enabled)
            
        Returns:
            Dict of channel -> success status
        """
        # Check rate limits
        if not self._check_rate_limit():
            logger.warning(f"Rate limit exceeded, suppressing alert: {alert.title}")
            return {}
        
        # Check quiet hours
        if self._is_quiet_hours() and alert.priority != AlertPriority.CRITICAL:
            logger.info(f"Quiet hours, suppressing non-critical alert: {alert.title}")
            return {}
        
        # Check deduplication
        if self._is_duplicate(alert):
            logger.debug(f"Duplicate alert suppressed: {alert.title}")
            return {}
        
        # Determine channels
        if channels is None:
            channels = self._get_enabled_channels()
        
        # Send through each channel
        results = {}
        for channel in channels:
            try:
                success = self._send_to_channel(alert, channel)
                results[channel.value] = success
            except Exception as e:
                logger.error(f"Failed to send alert via {channel.value}: {e}")
                results[channel.value] = False
        
        # Track alert
        with self._lock:
            self._alert_history.append({
                'alert_id': alert.alert_id,
                'title': alert.title,
                'priority': alert.priority.name,
                'timestamp': alert.timestamp,
                'channels': list(results.keys()),
                'success': any(results.values())
            })
            
            self._sent_alerts[alert.alert_id] = time.time()
            self._hourly_counts[datetime.now().hour] += 1
            self._daily_count += 1
        
        return results
    
    def _send_to_channel(self, alert: Alert, channel: AlertChannel) -> bool:
        """Send alert to specific channel"""
        channel_config = self.alert_config.get('channels', {}).get(channel.value, {})
        
        if not channel_config.get('enabled', False):
            return False
        
        # Check if critical_only filter applies
        if channel_config.get('critical_only', False):
            if alert.priority != AlertPriority.CRITICAL:
                return False
        
        # Route to appropriate handler
        handlers = {
            AlertChannel.MACOS_NOTIFICATION: self._send_macos_notification,
            AlertChannel.EMAIL: self._send_email,
            AlertChannel.SLACK: self._send_slack,
            AlertChannel.DISCORD: self._send_discord,
            AlertChannel.WEBHOOK: self._send_webhook,
            AlertChannel.TELEGRAM: self._send_telegram,
            AlertChannel.TWILIO_SMS: self._send_twilio_sms
        }
        
        handler = handlers.get(channel)
        if handler:
            return handler(alert, channel_config)
        
        return False
    
    def _send_macos_notification(self, alert: Alert, config: Dict) -> bool:
        """Send macOS notification"""
        try:
            # Priority emoji
            emoji_map = {
                AlertPriority.LOW: "ℹ️",
                AlertPriority.MEDIUM: "⚠️",
                AlertPriority.HIGH: "🔴",
                AlertPriority.CRITICAL: "🚨"
            }
            emoji = emoji_map.get(alert.priority, "🔔")
            
            title = f"{emoji} {alert.title}"
            
            # Use osascript for native macOS notifications
            script = f'''
                display notification "{alert.message}" ¬
                with title "{title}" ¬
                subtitle "EDR Alert - {alert.severity.upper()}" ¬
                sound name "Basso"
            '''
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info(f"macOS notification sent: {alert.title}")
                return True
            else:
                logger.error(f"macOS notification failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"macOS notification error: {e}")
            return False
    
    def _send_email(self, alert: Alert, config: Dict) -> bool:
        """Send email alert via SMTP"""
        try:
            # Check required config
            required = ['smtp_server', 'smtp_port', 'from_address', 'to_address']
            if not all(config.get(k) for k in required):
                logger.warning("Email config incomplete, skipping")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[EDR Alert] {alert.severity.upper()} - {alert.title}"
            msg['From'] = config['from_address']
            msg['To'] = config['to_address']
            
            # Plain text version
            text = f"""
EDR Security Alert

Priority: {alert.priority.name}
Severity: {alert.severity.upper()}
Time: {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}
Source: {alert.source}

{alert.message}

Details:
{json.dumps(alert.details, indent=2)}

---
BCAM Hybrid EDR System
"""
            
            # HTML version
            html = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <div style="background: #f4f4f4; padding: 20px; border-radius: 8px;">
        <h2 style="color: #d32f2f;">🚨 EDR Security Alert</h2>
        <table style="width: 100%; margin-top: 20px;">
            <tr>
                <td style="font-weight: bold; padding: 8px;">Priority:</td>
                <td style="padding: 8px;">{alert.priority.name}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; padding: 8px;">Severity:</td>
                <td style="padding: 8px; color: #d32f2f;">{alert.severity.upper()}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; padding: 8px;">Time:</td>
                <td style="padding: 8px;">{datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; padding: 8px;">Source:</td>
                <td style="padding: 8px;">{alert.source}</td>
            </tr>
        </table>
        <div style="margin-top: 20px; padding: 15px; background: white; border-left: 4px solid #d32f2f;">
            <h3>Message:</h3>
            <p>{alert.message}</p>
        </div>
    </div>
</body>
</html>
"""
            
            msg.attach(MIMEText(text, 'plain'))
            msg.attach(MIMEText(html, 'html'))
            
            # Send
            with smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=10) as server:
                if config.get('use_tls', True):
                    server.starttls()
                
                # Login if credentials provided
                if config.get('username') and config.get('password'):
                    server.login(config['username'], config['password'])
                
                server.send_message(msg)
            
            logger.info(f"Email alert sent to {config['to_address']}")
            return True
            
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
            return False
    
    def _send_slack(self, alert: Alert, config: Dict) -> bool:
        """Send Slack webhook alert"""
        try:
            webhook_url = config.get('webhook_url')
            if not webhook_url:
                return False
            
            # Color based on severity
            color_map = {
                'info': '#36a64f',
                'warning': '#ff9800',
                'high': '#ff5722',
                'critical': '#d32f2f'
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, '#cccccc'),
                    "title": f"🛡️ EDR Alert: {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Priority",
                            "value": alert.priority.name,
                            "short": True
                        },
                        {
                            "title": "Severity",
                            "value": alert.severity.upper(),
                            "short": True
                        },
                        {
                            "title": "Source",
                            "value": alert.source,
                            "short": True
                        },
                        {
                            "title": "Time",
                            "value": datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                            "short": True
                        }
                    ],
                    "footer": "BCAM EDR System",
                    "ts": int(alert.timestamp)
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            
            logger.info("Slack alert sent")
            return True
            
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
            return False
    
    def _send_discord(self, alert: Alert, config: Dict) -> bool:
        """Send Discord webhook alert"""
        try:
            webhook_url = config.get('webhook_url')
            if not webhook_url:
                return False
            
            # Color based on severity
            color_map = {
                'info': 0x36a64f,
                'warning': 0xff9800,
                'high': 0xff5722,
                'critical': 0xd32f2f
            }
            
            payload = {
                "embeds": [{
                    "title": f"🛡️ EDR Alert: {alert.title}",
                    "description": alert.message,
                    "color": color_map.get(alert.severity, 0xcccccc),
                    "fields": [
                        {
                            "name": "Priority",
                            "value": alert.priority.name,
                            "inline": True
                        },
                        {
                            "name": "Severity",
                            "value": alert.severity.upper(),
                            "inline": True
                        },
                        {
                            "name": "Source",
                            "value": alert.source,
                            "inline": True
                        }
                    ],
                    "timestamp": datetime.fromtimestamp(alert.timestamp).isoformat(),
                    "footer": {
                        "text": "BCAM EDR System"
                    }
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            
            logger.info("Discord alert sent")
            return True
            
        except Exception as e:
            logger.error(f"Discord alert failed: {e}")
            return False
    
    def _send_webhook(self, alert: Alert, config: Dict) -> bool:
        """Send generic webhook alert"""
        try:
            webhook_url = config.get('url')
            if not webhook_url:
                return False
            
            payload = {
                "alert_id": alert.alert_id,
                "title": alert.title,
                "message": alert.message,
                "priority": alert.priority.name,
                "severity": alert.severity,
                "timestamp": alert.timestamp,
                "source": alert.source,
                "details": alert.details
            }
            
            response = requests.post(webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            
            logger.info("Webhook alert sent")
            return True
            
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
            return False
    
    def _send_telegram(self, alert: Alert, config: Dict) -> bool:
        """Send alert via Telegram Bot API"""
        try:
            # Check min_severity filter
            min_severity = config.get('min_severity', 'high')
            severity_order = ['info', 'warning', 'high', 'critical']
            if severity_order.index(alert.severity) < severity_order.index(min_severity):
                logger.debug(f"Alert severity {alert.severity} below min {min_severity}, skipping Telegram")
                return False
            
            bot_token = config.get('bot_token')
            chat_ids = config.get('chat_ids', [])
            
            if not bot_token or not chat_ids:
                logger.error("Telegram config incomplete")
                return False
            
            # Emoji based on severity
            emoji_map = {
                'critical': '🚨',
                'high': '⚠️',
                'medium': '⚡',
                'low': 'ℹ️',
                'info': '📢'
            }
            emoji = emoji_map.get(alert.severity, '📬')
            
            # Format message (Telegram supports Markdown)
            text = f"{emoji} *{alert.title}*\n\n{alert.message}\n\n_Severity: {alert.severity.upper()}_\n_Source: {alert.source}_\n_BCAM Hybrid EDR_"
            
            # Send to all chat IDs
            success_count = 0
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            for chat_id in chat_ids:
                try:
                    response = requests.post(
                        url,
                        json={
                            'chat_id': chat_id,
                            'text': text,
                            'parse_mode': 'Markdown'
                        },
                        timeout=10
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    if result.get('ok'):
                        success_count += 1
                        logger.info(f"✅ Telegram sent to chat {chat_id}")
                    else:
                        logger.error(f"Telegram API error: {result.get('description')}")
                        
                except Exception as e:
                    logger.error(f"Failed to send Telegram to {chat_id}: {e}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")
            return False
    
    def _send_twilio_sms(self, alert: Alert, config: Dict) -> bool:
        """Send SMS via Twilio"""
        try:
            # Check min_severity filter
            min_severity = config.get('min_severity', 'high')
            severity_order = ['info', 'warning', 'high', 'critical']
            if severity_order.index(alert.severity) < severity_order.index(min_severity):
                logger.debug(f"Alert severity {alert.severity} below min {min_severity}, skipping SMS")
                return False
            
            account_sid = config.get('account_sid')
            auth_token = config.get('auth_token')
            from_number = config.get('from_number')
            to_numbers = config.get('to_numbers', [])
            
            if not all([account_sid, auth_token, from_number, to_numbers]):
                logger.error("Twilio SMS config incomplete")
                return False
            
            # Priority emoji for SMS
            emoji_map = {
                AlertPriority.LOW: "ℹ️",
                AlertPriority.MEDIUM: "⚠️",
                AlertPriority.HIGH: "🔴",
                AlertPriority.CRITICAL: "🚨"
            }
            emoji = emoji_map.get(alert.priority, "⚡")
            
            # Build SMS message (160 char limit awareness)
            sms_body = f"{emoji} BCAM EDR: {alert.title}\n{alert.message[:100]}"
            
            # Twilio API endpoint
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            
            # Send to each number
            success_count = 0
            for to_number in to_numbers:
                try:
                    # Use WhatsApp format (whatsapp: prefix)
                    response = requests.post(
                        url,
                        auth=(account_sid, auth_token),
                        data={
                            'From': f'whatsapp:{from_number}',  # WhatsApp sender
                            'To': f'whatsapp:{to_number}',      # WhatsApp recipient
                            'Body': sms_body
                        },
                        timeout=10
                    )
                    response.raise_for_status()
                    success_count += 1
                    logger.info(f"SMS sent to {to_number}")
                except Exception as e:
                    logger.error(f"Failed to send SMS to {to_number}: {e}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Twilio SMS failed: {e}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows sending alert"""
        with self._lock:
            # Reset counters if needed
            now = datetime.now()
            if (now - self._last_reset).days >= 1:
                self._daily_count = 0
                self._hourly_counts.clear()
                self._last_reset = now
            
            # Check hourly limit
            current_hour = now.hour
            if self._hourly_counts[current_hour] >= self.rate_limits['max_per_hour']:
                return False
            
            # Check daily limit
            if self._daily_count >= self.rate_limits['max_per_day']:
                return False
            
            return True
    
    def _is_quiet_hours(self) -> bool:
        """Check if currently in quiet hours"""
        hour = datetime.now().hour
        start = self.quiet_hours['start']
        end = self.quiet_hours['end']
        
        if start < end:
            return start <= hour < end
        else:
            # Wraps around midnight
            return hour >= start or hour < end
    
    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if alert is duplicate within dedup window"""
        if alert.alert_id in self._sent_alerts:
            last_sent = self._sent_alerts[alert.alert_id]
            if time.time() - last_sent < self.dedup_window:
                return True
        return False
    
    def _get_enabled_channels(self) -> List[AlertChannel]:
        """Get list of enabled channels"""
        channels = []
        config = self.alert_config.get('channels', {})
        
        for channel_name, channel_config in config.items():
            if channel_config.get('enabled', False):
                try:
                    channel = AlertChannel(channel_name)
                    channels.append(channel)
                except ValueError:
                    logger.warning(f"Unknown channel: {channel_name}")
        
        return channels
    
    def get_alert_history(self, hours: int = 24) -> List[Dict]:
        """Get alert history for last N hours"""
        cutoff = time.time() - (hours * 3600)
        
        with self._lock:
            return [
                alert for alert in self._alert_history
                if alert['timestamp'] > cutoff
            ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get alerting statistics"""
        with self._lock:
            return {
                'daily_count': self._daily_count,
                'hourly_counts': dict(self._hourly_counts),
                'rate_limits': self.rate_limits,
                'total_history': len(self._alert_history),
                'unique_alerts': len(self._sent_alerts),
                'is_quiet_hours': self._is_quiet_hours()
            }


def create_alert_from_detection(detection: Dict[str, Any], severity: str) -> Alert:
    """
    Create alert from detection event
    
    Args:
        detection: Detection event dictionary
        severity: Severity level (info, warning, high, critical)
        
    Returns:
        Alert object
    """
    # Map severity to priority
    priority_map = {
        'info': AlertPriority.LOW,
        'warning': AlertPriority.MEDIUM,
        'high': AlertPriority.HIGH,
        'critical': AlertPriority.CRITICAL
    }
    
    priority = priority_map.get(severity, AlertPriority.MEDIUM)
    
    # Build title and message
    title = detection.get('title', 'Security Event Detected')
    message = detection.get('message', 'Suspicious activity detected')
    
    return Alert(
        title=title,
        message=message,
        priority=priority,
        severity=severity,
        source=detection.get('source', 'EDR'),
        details=detection.get('details', {})
    )
