import smtplib
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import structlog
from typing import Optional, List, Dict
from datetime import datetime

logger = structlog.get_logger()

class NotificationService:
    """Service to handle email and other notifications for security events."""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.smtp_from = os.getenv("SMTP_FROM", "surveillance@system.ai")
        self.recipient = os.getenv("NOTIFICATION_RECIPIENT")
        
        self.enabled = all([self.smtp_user, self.smtp_pass, self.recipient])
        if not self.enabled:
            logger.warning("Notification service partially configured. Emails will be logged but not sent.")
            logger.warning(f"Missing: {'SMTP_USER ' if not self.smtp_user else ''}{'SMTP_PASS ' if not self.smtp_pass else ''}{'RECIPIENT' if not self.recipient else ''}")

    async def send_event_email(self, event: Dict, camera_name: str = "Unknown"):
        """Send an email notification for a security event."""
        if not self.enabled:
            logger.info(f"[MOCK EMAIL] To: {self.recipient} | Subject: Security Alert: {event['event_type']}")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from
            msg['To'] = self.recipient
            msg['Subject'] = f"🚨 Security Alert: {event['event_type'].upper()} on {camera_name}"

            # Create body
            timestamp = event.get('start_time', datetime.now().isoformat())
            severity = event.get('severity', 'medium').upper()
            
            body = f"""
            <h2>Security Event Detected</h2>
            <p><strong>Type:</strong> {event['event_type'].replace('_', ' ').title()}</p>
            <p><strong>Camera:</strong> {camera_name}</p>
            <p><strong>Time:</strong> {timestamp}</p>
            <p><strong>Severity:</strong> <span style="color: {'red' if severity == 'HIGH' else 'orange'}">{severity}</span></p>
            <p><strong>Details:</strong></p>
            <ul>
            """
            
            for k, v in event.get('event_data', {}).items():
                body += f"<li>{k.replace('_', ' ').title()}: {v}</li>"
            
            body += "</ul><br><p>Please check the live feed for more information.</p>"
            
            msg.attach(MIMEText(body, 'html'))

            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
                
            logger.info(f"Email notification sent for event {event['id']}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

notification_service = NotificationService()
