#!/usr/bin/env python3
"""
Telegram Bot Alerting - Completely Free
- Works globally
- No message limits
- Instant push notifications
- Works on phone, desktop, web
"""
import requests
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class TelegramAlerter:
    """Send alerts via Telegram Bot API"""
    
    def __init__(self, config: dict):
        self.config = config
        telegram_config = config.get('alerting', {}).get('telegram', {})
        
        self.enabled = telegram_config.get('enabled', False)
        self.bot_token = telegram_config.get('bot_token')
        self.chat_ids = telegram_config.get('chat_ids', [])
        self.min_severity = telegram_config.get('min_severity', 'high')
        
        if self.enabled and not self.bot_token:
            logger.warning("Telegram enabled but no bot_token configured")
            self.enabled = False
        
        if self.enabled and not self.chat_ids:
            logger.warning("Telegram enabled but no chat_ids configured")
            self.enabled = False
        
        if self.enabled:
            logger.info(f"Telegram alerter initialized: {len(self.chat_ids)} recipient(s)")
    
    def send_alert(self, title: str, message: str, severity: str = 'medium'):
        """Send alert via Telegram"""
        
        if not self.enabled:
            return
        
        # Check severity filter
        severity_levels = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        if severity_levels.get(severity, 0) < severity_levels.get(self.min_severity, 2):
            return
        
        # Format message with emoji based on severity
        emoji = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '⚡',
            'low': 'ℹ️',
            'info': '📢'
        }.get(severity, '📬')
        
        text = f"{emoji} *{title}*\n\n{message}\n\n_Severity: {severity.upper()}_\n_BCAM Hybrid EDR_"
        
        # Send to all configured chat IDs
        success_count = 0
        for chat_id in self.chat_ids:
            try:
                self._send_message(chat_id, text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send Telegram to {chat_id}: {e}")
        
        if success_count > 0:
            logger.info(f"✅ Telegram alert sent to {success_count}/{len(self.chat_ids)} recipient(s)")
    
    def _send_message(self, chat_id: str, text: str):
        """Send message to specific chat"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if not result.get('ok'):
            raise Exception(f"Telegram API error: {result.get('description')}")
    
    def test(self):
        """Send test message"""
        self.send_alert(
            title="✅ BCAM EDR Test Alert",
            message="Telegram alerting is working!\n\nYou'll receive UPS disconnect alerts here.",
            severity="medium"
        )
        print("✅ Test alert sent to Telegram")
    
    def get_bot_info(self) -> Optional[dict]:
        """Get bot information (useful for verification)"""
        if not self.bot_token:
            return None
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get bot info: {e}")
            return None


# Quick setup helper
def setup_telegram_bot():
    """Interactive setup helper"""
    print("=" * 60)
    print("Telegram Bot Setup for BCAM EDR")
    print("=" * 60)
    print()
    print("📱 Step 1: Create a Telegram Bot")
    print("   1. Open Telegram app")
    print("   2. Search for @BotFather")
    print("   3. Send: /newbot")
    print("   4. Follow prompts to create your bot")
    print("   5. Copy the bot token (looks like: 123456:ABC-DEF...)")
    print()
    print("💬 Step 2: Get Your Chat ID")
    print("   1. Search for @userinfobot in Telegram")
    print("   2. Send it any message")
    print("   3. It will reply with your chat ID (looks like: 123456789)")
    print()
    print("⚙️  Step 3: Configure EDR")
    print("   Edit: config/config.yaml")
    print("   Add under 'alerting:':")
    print()
    print("   telegram:")
    print("     enabled: true")
    print("     bot_token: \"YOUR_BOT_TOKEN_HERE\"")
    print("     chat_ids:")
    print("       - \"YOUR_CHAT_ID_HERE\"")
    print("     min_severity: \"high\"")
    print()
    print("=" * 60)


if __name__ == '__main__':
    setup_telegram_bot()
