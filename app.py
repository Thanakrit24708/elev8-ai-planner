import os
import sys
from typing import Dict, Any, List, Optional
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Relax OAuth token scope checks so Google scope aliases are accepted
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from src.config import Config
from src.utils.logger import logger
from src.services.db_service import DatabaseService
from src.services.classroom_service import ClassroomService
from src.services.ai_service import AIService
from src.services.validation_service import ValidationService
from src.services.notification_service import NotificationService

app = Flask(__name__)
app.secret_key = "automated_project_planner_secret_key"

# Ensure database tables exist on startup
try:
    DatabaseService.init_database()
except Exception as e:
    logger.warning(f"Database initialization warning on app start: {e}")

import time

# Cache for classroom assignments to avoid re-fetching on every page reload
CACHED_ASSIGNMENTS: List[Dict[str, Any]] = []
CACHED_BRIEFING: Optional[str] = None
CACHED_BRIEFING_TIME: float = 0.0
CACHED_COURSES: List[Dict[str, Any]] = []
CACHED_COURSES_TIME: float = 0.0

def get_dashboard_courses(projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Retrieves courses for currently loaded projects."""
    course_map: Dict[str, Dict[str, Any]] = {}

    for p in projects:
        c_name = p.get("course_name")
        if c_name:
            if c_name not in course_map:
                course_map[c_name] = {"name": c_name, "project_count": 0}
            course_map[c_name]["project_count"] += 1

    return list(course_map.values())

@app.route("/")
def dashboard():
    """Phase 4: Dynamic Real-time Dashboard View."""
    try:
        metrics = DatabaseService.get_dashboard_metrics()
        projects = DatabaseService.get_all_projects()
        today_tasks = DatabaseService.get_today_focus_tasks()
        upcoming = DatabaseService.get_upcoming_deadlines()
        enrolled_courses = get_dashboard_courses(projects)

        # Smart Dynamic Briefing (Instant & Free - No API Call/Token Cost)
        if today_tasks:
            high_count = sum(1 for t in today_tasks if str(t.get("priority", "")).upper() == "HIGH")
            hours_sum = sum(float(t.get("estimated_hours", 1) or 1) for t in today_tasks)
            ai_briefing = f"วันนี้มีงานที่ต้องโฟกัส {len(today_tasks)} งาน (งานด่วน {high_count} งาน) รวมเวลาประเมิน {hours_sum:.1f} ชม. จัดการตามลำดับความสำคัญได้เลยครับ!"
        else:
            ai_briefing = "ยินดีด้วยครับ! ไม่มีงานค้างสำหรับวันนี้ คุณสามารถนำการบ้านใหม่จาก Google Classroom เข้ามาวางแผนได้เลยครับ"

        return render_template(
            "dashboard.html",
            metrics=metrics,
            projects=projects,
            today_tasks=today_tasks,
            upcoming=upcoming,
            ai_briefing=ai_briefing,
            enrolled_courses=enrolled_courses
        )
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return render_template(
            "dashboard.html",
            metrics={"total_assignments": 0, "total_subtasks": 0, "done_subtasks": 0, "in_progress_subtasks": 0, "todo_subtasks": 0, "total_hours": 0, "completion_rate": 0},
            projects=[],
            today_tasks=[],
            upcoming=[],
            ai_briefing="ไม่สามารถโหลดข้อมูลได้ในขณะนี้",
            enrolled_courses=[]
        )

@app.route("/classroom")
def classroom_view():
    """Phase 0: Google Classroom Ingestion View with Checkbox selection."""
    return render_template("classroom.html")

@app.route("/project/<assignment_id>")
def project_detail(assignment_id: str):
    """View full details and manage subtasks of a single project."""
    project = DatabaseService.get_assignment_with_subtasks(assignment_id)
    if not project:
        return redirect(url_for("dashboard"))
    return render_template("project_detail.html", project=project)

# ==========================================
# REST APIs
# ==========================================

@app.route("/api/classroom/fetch", methods=["POST"])
def api_fetch_classroom():
    """Fetches assignments from Google Classroom with option to refresh cache."""
    global CACHED_ASSIGNMENTS
    force_refresh = request.json.get("refresh", False) if request.is_json else False

    if CACHED_ASSIGNMENTS and not force_refresh:
        return jsonify({"success": True, "assignments": CACHED_ASSIGNMENTS, "cached": True})

    try:
        service = ClassroomService()
        assignments = service.fetch_all_assignments()

        # Mark which ones are already processed in DB
        for a in assignments:
            try:
                a["is_processed"] = DatabaseService.is_assignment_processed(a["id"])
            except Exception as e:
                logger.warning(f"Could not check processed status for assignment {a.get('id')}: {e}")
                a["is_processed"] = False

        CACHED_ASSIGNMENTS = assignments
        return jsonify({"success": True, "assignments": assignments, "cached": False})
    except Exception as e:
        logger.error(f"Classroom fetch error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/plan/validate-and-generate", methods=["POST"])
def api_validate_and_generate_plan():
    """
    Phase 1 & Phase 2:
    Runs AI Decomposition + Automated Validation Loop.
    Supports either n8n Webhook Workflow (if N8N_WEBHOOK_URL is set) or native Python engine.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    data = request.get_json()
    if not data or "assignment" not in data:
        return jsonify({"success": False, "error": "Missing assignment payload"}), 400

    assignment = data["assignment"]
    logger.info(f"Generating AI plan for '{assignment.get('title')}'")

    # 1. Check if n8n Webhook is configured
    n8n_url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    if n8n_url:
        try:
            import requests
            logger.info(f"[N8N] Dispatching planning request to Webhook: {n8n_url}")
            n8n_payload = {
                "assignment_id": str(assignment.get("id") or ""),
                "course_id": str(assignment.get("course_id") or ""),
                "course_name": assignment.get("course_name") or "General Course",
                "project_name": assignment.get("title"),
                "goal_description": assignment.get("description") or assignment.get("title"),
                "deadline": assignment.get("due_date"),
                "alternate_link": assignment.get("alternate_link") or "",
                "team_members": [{"name": "Student", "email": Config.NOTIFICATION_RECIPIENT}]
            }
            logger.info(f"[N8N] Payload sent: {n8n_payload}")
            n8n_resp = requests.post(n8n_url, json=n8n_payload, timeout=60)
            logger.info(f"[N8N] Response status: {n8n_resp.status_code}")
            if n8n_resp.status_code == 200:
                n8n_data = n8n_resp.json()
                blueprint = n8n_data.get("blueprint", {})
                validation = n8n_data.get("validation", {})
                
                formatted_subtasks = []
                for idx, t in enumerate(blueprint.get("subtasks", []), start=1):
                    formatted_subtasks.append({
                        "task_order": idx,
                        "task_title": t.get("title") or t.get("task_title", f"Task #{idx}"),
                        "description": f"Assignee: {t.get('assignee', 'Me')} | Dependencies: {', '.join(t.get('dependencies', []))}",
                        "priority": (t.get("priority") or "MEDIUM").upper(),
                        "estimated_hours": float(t.get("estimated_hours", 1.0)),
                        "suggested_due_date": assignment.get("due_date")
                    })

                result = {
                    "passed": validation.get("is_valid", True),
                    "iterations_used": validation.get("retry_count", 1),
                    "max_iterations": 3,
                    "plan": {
                        "project_summary": f"แผนงานประมวลผลผ่าน n8n Workflow (สถานะ: {n8n_data.get('status')})",
                        "subtasks": formatted_subtasks
                    },
                    "feedbacks": validation.get("errors", []),
                    "needs_manual_review": validation.get("manual_review_required", False)
                }
                return jsonify({"success": True, "result": result, "source": "n8n"})
            else:
                logger.warning(f"n8n webhook returned status {n8n_resp.status_code}. Falling back to internal engine.")
        except Exception as n8n_err:
            logger.warning(f"Could not connect to n8n ({n8n_err}). Falling back to internal engine.")

    # 2. Native AI Service with Validation Loop
    try:
        ai_service = AIService()
        result = ai_service.analyze_assignment_with_validation_loop(assignment, max_iterations=3)
        return jsonify({"success": True, "result": result, "source": "python"})
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/plan/save", methods=["POST"])
def api_save_plan():
    """
    Phase 3: Human Review & Persistence
    Receives approved / edited subtasks from the user, saves to DB,
    and optionally dispatches email notification.
    """
    data = request.get_json()
    if not data or "assignment" not in data or "subtasks" not in data:
        return jsonify({"success": False, "error": "Invalid payload"}), 400

    assignment = data["assignment"]
    subtasks = data["subtasks"]
    send_email = data.get("send_email", True)
    summary = data.get("summary", "")

    try:
        assignment_id = assignment["id"]
        # Save raw assignment
        DatabaseService.save_assignment(assignment)
        # Save subtasks & mark PROCESSED
        DatabaseService.save_subtasks(assignment_id, subtasks)

        # Send Email Notification if requested
        email_sent = False
        if send_email and Config.validate_smtp_config():
            try:
                email_sent = NotificationService.send_assignment_summary(
                    assignment=assignment,
                    subtasks=subtasks,
                    summary=summary
                )
            except Exception as mail_err:
                logger.warning(f"Could not send email for {assignment_id}: {mail_err}")

        # Update cache status
        global CACHED_ASSIGNMENTS
        for a in CACHED_ASSIGNMENTS:
            if a["id"] == assignment_id:
                a["is_processed"] = True

        return jsonify({
            "success": True,
            "assignment_id": assignment_id,
            "email_sent": email_sent
        })
    except Exception as e:
        logger.error(f"Failed to persist plan: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/subtasks/<subtask_id>/status", methods=["POST"])
@app.route("/api/subtask/<subtask_id>/status", methods=["POST"])
def api_update_subtask_status(subtask_id: str):
    """Phase 4: Real-time subtask status transition (TODO, IN_PROGRESS, DONE)."""
    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"success": False, "error": "Missing status"}), 400

    new_status = data["status"]
    try:
        updated = DatabaseService.update_subtask_status(subtask_id, new_status)
        if not updated:
            return jsonify({"success": False, "error": f"ไม่พบงานรหัส {subtask_id} ใน Google Sheets"}), 404
        return jsonify({"success": True, "subtask_id": subtask_id, "new_status": new_status})
    except Exception as e:
        logger.error(f"Failed to update subtask status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/dashboard/stats", methods=["GET"])
def api_dashboard_stats():
    """Phase 4: Real-time dashboard statistics API."""
    try:
        metrics = DatabaseService.get_dashboard_metrics()
        today_tasks = DatabaseService.get_today_focus_tasks()
        return jsonify({"success": True, "metrics": metrics, "today_tasks": today_tasks})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/clear-data", methods=["POST"])
def api_clear_data():
    """Clears all Assignments and Subtasks from Google Sheets (for testing cleanup)."""
    global CACHED_ASSIGNMENTS, CACHED_BRIEFING, CACHED_BRIEFING_TIME
    try:
        from src.services.sheet_service import SheetService
        result = SheetService.clear_all_data()
        CACHED_ASSIGNMENTS.clear()
        CACHED_BRIEFING = None
        CACHED_BRIEFING_TIME = 0.0
        return jsonify({
            "success": True,
            "deleted": result,
            "message": f"ลบข้อมูลทั้งหมดแล้ว: งาน {result['assignments']} รายการ, subtask {result['subtasks']} รายการ"
        })
    except Exception as e:
        logger.error(f"Failed to clear data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    logger.info("Starting Automated Project Planner Web Server on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=True)

