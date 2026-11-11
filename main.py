import argparse
import os
import sys

# Relax OAuth token scope checks so Google scope aliases are accepted cleanly
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from typing import List, Dict, Any

from src.config import Config
from src.utils.logger import logger
from src.services.db_service import DatabaseService
from src.services.classroom_service import ClassroomService
from src.services.ai_service import AIService
from src.services.notification_service import NotificationService

def run_init_database():
    """Initializes the database schema."""
    logger.info("Initializing MariaDB database...")
    try:
        DatabaseService.init_database()
        logger.info("Database initialization completed successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

def run_test_email():
    """Sends a mock verification email to confirm SMTP settings."""
    logger.info("Sending test notification email...")
    dummy_assignment = {
        "id": "TEST_001",
        "title": "Sample Graduation Capstone Project",
        "course_name": "CS401: Advanced Software Engineering",
        "due_date": "2026-11-15 23:59:00",
        "alternate_link": "https://classroom.google.com"
    }
    dummy_subtasks = [
        {
            "task_order": 1,
            "task_title": "Requirement Gathering & Architecture Spec",
            "description": "Document system use cases and finalize data models.",
            "priority": "HIGH",
            "estimated_hours": 4.0,
            "suggested_due_date": "2026-11-02 18:00:00"
        },
        {
            "task_order": 2,
            "task_title": "Database Schema Setup & API Prototyping",
            "description": "Set up MariaDB migrations and draft REST endpoint routes.",
            "priority": "MEDIUM",
            "estimated_hours": 6.5,
            "suggested_due_date": "2026-11-08 18:00:00"
        },
        {
            "task_order": 3,
            "task_title": "Integration Testing & Final Presentation Prep",
            "description": "Perform end-to-end testing and prepare slide deck.",
            "priority": "LOW",
            "estimated_hours": 3.0,
            "suggested_due_date": "2026-11-14 20:00:00"
        }
    ]
    summary = "This is a verification test to ensure Gmail SMTP delivery is functioning properly with App Password authentication."

    try:
        success = NotificationService.send_assignment_summary(dummy_assignment, dummy_subtasks, summary)
        if success:
            logger.info("Test email delivered successfully! Please check your inbox.")
        else:
            logger.warning("Test email was not delivered. Check your SMTP settings in .env.")
    except Exception as e:
        logger.error(f"Test email failed: {e}")

def run_workflow(
    force_reprocess: bool = False,
    dry_run: bool = False,
    send_notification: bool = True,
    limit: int = 0,
    course_id: str = None
):
    """
    Executes the end-to-end Automated Project Planning workflow:
    1. Connect to Classroom API & pull assignments
    2. Filter out already processed assignments (unless force_reprocess)
    3. Run AI planning decomposition for each assignment
    4. Store results in MariaDB
    5. Send summary email notification
    """
    logger.info("==================================================")
    logger.info("🚀 Starting Automated Project Planning Workflow")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'} | Force: {force_reprocess} | Limit: {limit or 'ALL'}")
    logger.info("==================================================")

    # Step 1: Initialize Database if live mode
    if not dry_run:
        try:
            DatabaseService.init_database()
        except Exception as e:
            logger.error(f"Could not connect to storage: {e}.")
            return

    # Step 2: Fetch Assignments from Google Classroom
    classroom_service = ClassroomService()
    try:
        assignments = classroom_service.fetch_all_assignments()
    except Exception as e:
        logger.error(f"Failed to fetch assignments from Google Classroom: {e}")
        return

    if not assignments:
        logger.info("No assignments found to process.")
        return

    # Filter by specific course_id if provided via CLI
    if course_id:
        assignments = [a for a in assignments if str(a.get("course_id")) == str(course_id)]

    logger.info(f"Retrieved {len(assignments)} assignment(s) across courses.")

    # Apply limit if specified
    if limit > 0:
        assignments = assignments[:limit]
        logger.info(f"Limiting processing to the first {len(assignments)} assignment(s).")

    ai_service = AIService()
    processed_count = 0
    skipped_count = 0

    # Step 3: Process each assignment
    for assignment in assignments:
        assignment_id = assignment["id"]
        title = assignment["title"]

        if not force_reprocess and not dry_run:
            if DatabaseService.is_assignment_processed(assignment_id):
                logger.info(f"Skipping '{title}' (ID: {assignment_id}) - Already processed.")
                skipped_count += 1
                continue

        logger.info(f"--- Processing Assignment: {title} (ID: {assignment_id}) ---")

        if dry_run:
            logger.info(f"[DRY-RUN] Would process assignment: {title}")
            continue

        try:
            # Save raw assignment with PENDING status
            DatabaseService.save_assignment(assignment)

            # Analyze with AI
            plan = ai_service.analyze_assignment(assignment)
            subtasks_dict_list = [task.model_dump() for task in plan.subtasks]

            # Save subtasks and mark PROCESSED
            DatabaseService.save_subtasks(assignment_id, subtasks_dict_list)

            # Send Email Notification
            if send_notification:
                try:
                    NotificationService.send_assignment_summary(
                        assignment=assignment,
                        subtasks=subtasks_dict_list,
                        summary=plan.project_summary
                    )
                except Exception as mail_err:
                    logger.warning(f"Failed to send email notification for {assignment_id}: {mail_err}")

            processed_count += 1

        except Exception as e:
            logger.error(f"Error processing assignment '{title}': {e}")
            DatabaseService.log_execution(
                action="ASSIGNMENT_WORKFLOW",
                status="FAILED",
                details=f"Assignment {assignment_id} failed",
                error_message=str(e)
            )

    logger.info("==================================================")
    logger.info(f"Workflow Finished! Processed: {processed_count}, Skipped: {skipped_count}")
    logger.info("==================================================")


def main():
    parser = argparse.ArgumentParser(description="Automated Project Planning Backend Workflow")
    parser.add_argument("--sync", action="store_true", help="Run the full synchronization and planning workflow")
    parser.add_argument("--init-db", action="store_true", help="Initialize MariaDB database tables")
    parser.add_argument("--test-email", action="store_true", help="Send a test email notification")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of assignments to process (e.g. --limit 1)")
    parser.add_argument("--course-id", type=str, default=None, help="Filter by specific Google Classroom Course ID")
    parser.add_argument("--force", action="store_true", help="Force re-processing of already processed assignments")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to database or sending notifications")
    parser.add_argument("--no-notify", action="store_true", help="Skip sending email notifications")

    args = parser.parse_args()

    if args.init_db:
        run_init_database()
    elif args.test_email:
        run_test_email()
    elif args.sync or len(sys.argv) == 1 or args.limit or args.course_id or args.dry_run:
        # Default behavior: run workflow
        run_workflow(
            force_reprocess=args.force,
            dry_run=args.dry_run,
            send_notification=not args.no_notify,
            limit=args.limit,
            course_id=args.course_id
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
