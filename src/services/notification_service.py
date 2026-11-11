import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List

from src.config import Config
from src.utils.logger import logger
from src.utils.retry import retry_api_call
from src.services.db_service import DatabaseService

class NotificationService:
    """Service to send structured project planning summaries via Gmail SMTP."""

    @staticmethod
    def _generate_html_content(assignment: Dict[str, Any], subtasks: List[Dict[str, Any]], summary: str) -> str:
        """Constructs an aesthetic, responsive HTML email template."""
        title = assignment.get("title", "Untitled Assignment")
        course_name = assignment.get("course_name", "General Course")
        due_date = assignment.get("due_date") or "Not Specified"
        link = assignment.get("alternate_link", "")

        total_hours = sum(t.get("estimated_hours", 0) for t in subtasks)

        # Generate rows for each subtask
        rows_html = ""
        for task in subtasks:
            priority = task.get("priority", "MEDIUM").upper()
            badge_color = "#e53e3e" if priority == "HIGH" else ("#dd6b20" if priority == "MEDIUM" else "#38a169")

            rows_html += f"""
            <tr style="border-bottom: 1px solid #edf2f7;">
                <td style="padding: 12px; font-weight: bold; color: #4a5568; text-align: center;">#{task.get('task_order', 1)}</td>
                <td style="padding: 12px;">
                    <div style="font-weight: 600; color: #2d3748; font-size: 15px;">{task.get('task_title')}</div>
                    <div style="color: #718096; font-size: 13px; margin-top: 4px;">{task.get('description', '')}</div>
                </td>
                <td style="padding: 12px; text-align: center;">
                    <span style="background-color: {badge_color}; color: #ffffff; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">
                        {priority}
                    </span>
                </td>
                <td style="padding: 12px; text-align: center; color: #4a5568; font-size: 14px;">{task.get('estimated_hours', 1.0)}h</td>
                <td style="padding: 12px; text-align: right; color: #4a5568; font-size: 13px;">
                    {task.get('suggested_due_date') or '-'}
                </td>
            </tr>
            """

        link_button = ""
        if link:
            link_button = f"""
            <div style="margin-top: 20px; text-align: center;">
                <a href="{link}" style="background-color: #3182ce; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block;">
                    View in Google Classroom
                </a>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Project Plan: {title}</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f7fafc; margin: 0; padding: 24px; color: #2d3748;">
            <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 10px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%); padding: 24px 28px; color: #ffffff;">
                    <span style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9; font-weight: 600;">Automated Project Planning</span>
                    <h1 style="margin: 8px 0 4px 0; font-size: 22px; font-weight: 700;">{title}</h1>
                    <p style="margin: 0; font-size: 14px; opacity: 0.95;">Course: <strong>{course_name}</strong> | Due: <strong>{due_date}</strong></p>
                </div>

                <!-- Summary Body -->
                <div style="padding: 24px 28px;">
                    <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 14px 16px; border-radius: 4px; margin-bottom: 24px;">
                        <h3 style="margin: 0 0 6px 0; color: #2b6cb0; font-size: 14px; text-transform: uppercase;">AI Strategy Summary</h3>
                        <p style="margin: 0; color: #2d3748; font-size: 14px; line-height: 1.5;">{summary}</p>
                    </div>

                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h2 style="font-size: 16px; color: #1a202c; margin: 0;">Task Breakdown & Milestones</h2>
                        <span style="font-size: 13px; color: #718096; font-weight: 600;">Total Estimate: ~{total_hours:.1f} Hours</span>
                    </div>

                    <!-- Tasks Table -->
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                        <thead>
                            <tr style="background-color: #f7fafc; border-bottom: 2px solid #e2e8f0; color: #718096; font-size: 12px; text-transform: uppercase;">
                                <th style="padding: 10px; text-align: center; width: 40px;">#</th>
                                <th style="padding: 10px;">Subtask & Description</th>
                                <th style="padding: 10px; text-align: center; width: 80px;">Priority</th>
                                <th style="padding: 10px; text-align: center; width: 60px;">Hours</th>
                                <th style="padding: 10px; text-align: right; width: 140px;">Target Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>

                    {link_button}
                </div>

                <!-- Footer -->
                <div style="background-color: #edf2f7; padding: 14px 28px; text-align: center; font-size: 12px; color: #a0aec0;">
                    Generated automatically by Google Classroom AI Project Planner &bull; Powered by MariaDB & Gemini/Chat API
                </div>
            </div>
        </body>
        </html>
        """
        return html

    @classmethod
    @retry_api_call(action_name="SEND_EMAIL_NOTIFICATION")
    def _send_mail_via_smtp(cls, msg: MIMEMultipart, recipient: str):
        """Dispatches SMTP message with SSL/STARTTLS and retry logic."""
        if Config.SMTP_PORT == 465:
            # SSL Connection
            server = smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30)
        else:
            # STARTTLS Connection (Default 587)
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30)
            server.ehlo()
            if Config.SMTP_USE_TLS:
                server.starttls()
                server.ehlo()

        server.login(Config.SMTP_USER, Config.SMTP_APP_PASSWORD)
        server.sendmail(Config.SMTP_USER, [recipient], msg.as_string())
        server.quit()

    @classmethod
    def send_assignment_summary(
        cls,
        assignment: Dict[str, Any],
        subtasks: List[Dict[str, Any]],
        summary: str = ""
    ) -> bool:
        """
        Sends an email notification with assignment plan summary to the configured recipient.
        """
        if not Config.validate_smtp_config():
            logger.warning("SMTP configuration is incomplete in .env. Skipping email notification.")
            return False

        title = assignment.get("title", "Assignment Plan")
        course_name = assignment.get("course_name", "")
        recipient = Config.NOTIFICATION_RECIPIENT

        logger.info(f"Preparing email summary for '{title}' to {recipient}...")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📋 [Project Plan] {course_name}: {title}"
        msg["From"] = f"Classroom Project Planner <{Config.SMTP_USER}>"
        msg["To"] = recipient

        # Plain text fallback
        plain_text = f"Project Plan for: {title}\nCourse: {course_name}\nDue Date: {assignment.get('due_date')}\n\n"
        plain_text += f"Summary:\n{summary}\n\nTasks:\n"
        for t in subtasks:
            plain_text += f"#{t.get('task_order')}: {t.get('task_title')} [{t.get('priority')}] (~{t.get('estimated_hours')}h) - Due: {t.get('suggested_due_date')}\n"

        html_body = cls._generate_html_content(assignment, subtasks, summary)

        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            cls._send_mail_via_smtp(msg, recipient)
            logger.info(f"Email summary sent successfully to {recipient}.")
            DatabaseService.log_execution(
                action="EMAIL_NOTIFICATION",
                status="SUCCESS",
                details=f"Notification delivered for '{title}' to {recipient}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to deliver email notification to {recipient}: {e}")
            DatabaseService.log_execution(
                action="EMAIL_NOTIFICATION",
                status="FAILED",
                details=f"Failed for '{title}' to {recipient}",
                error_message=str(e)
            )
            raise e
