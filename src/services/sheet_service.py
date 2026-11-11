import os
import json
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import Config
from src.utils.logger import logger

class SheetService:
    """
    Google Sheets persistence service matching DatabaseService interface.
    Stores Assignments, Subtasks, and ExecutionLogs in a Google Spreadsheet.
    """

    ASSIGNMENTS_TAB = "Assignments"
    SUBTASKS_TAB = "Subtasks"
    LOGS_TAB = "ExecutionLogs"

    ASSIGNMENTS_HEADERS = [
        "id", "course_id", "course_name", "title", "description",
        "due_date", "alternate_link", "status", "created_at"
    ]

    SUBTASKS_HEADERS = [
        "id", "assignment_id", "task_order", "task_title", "description",
        "priority", "estimated_hours", "suggested_start_date", "suggested_due_date", "status"
    ]

    LOGS_HEADERS = [
        "id", "action", "status", "retry_count", "details", "error_message", "created_at"
    ]

    _thread_local = threading.local()
    _spreadsheet_id = None
    _rows_cache = {}
    _cache_ttl = 5.0  # Cache for 5 seconds to prevent multiple redundant API calls per page render

    @classmethod
    def get_credentials(cls) -> Credentials:
        """Obtains valid OAuth 2.0 credentials for Google Sheets."""
        token_path = Config.GOOGLE_TOKEN_FILE
        credentials_path = Config.GOOGLE_CLIENT_SECRETS_FILE
        creds = None

        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, Config.GOOGLE_SCOPES)
                if not creds.has_scopes(Config.GOOGLE_SCOPES):
                    logger.info("[Google Sheets] Token missing spreadsheet scope. Re-authenticating...")
                    creds = None
            except Exception as e:
                logger.warning(f"[Google Sheets] Could not load token file: {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"[Google Sheets] Could not refresh token: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Google OAuth credentials file '{credentials_path}' not found!"
                    )
                logger.info("[Google Sheets] Requesting user authorization for Google Sheets...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, Config.GOOGLE_SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        return creds

    @classmethod
    def get_service(cls):
        """Returns thread-safe Sheets API client."""
        if not hasattr(cls._thread_local, "service") or cls._thread_local.service is None:
            creds = cls.get_credentials()
            cls._thread_local.service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return cls._thread_local.service

    @classmethod
    def get_spreadsheet_id(cls) -> str:
        """Returns configured or detected Google Spreadsheet ID."""
        if cls._spreadsheet_id:
            return cls._spreadsheet_id

        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip() or Config.GOOGLE_SHEET_ID.strip()
        if sheet_id:
            cls._spreadsheet_id = sheet_id
            return sheet_id

        # Auto-create spreadsheet if none configured
        sheet_id = cls.create_new_spreadsheet()
        cls._spreadsheet_id = sheet_id
        return sheet_id

    @classmethod
    def create_new_spreadsheet(cls) -> str:
        """Creates a new Google Spreadsheet and saves ID to .env file."""
        service = cls.get_service()
        spreadsheet_body = {
            "properties": {"title": "Project Planner - Database"},
            "sheets": [
                {"properties": {"title": cls.ASSIGNMENTS_TAB}},
                {"properties": {"title": cls.SUBTASKS_TAB}},
                {"properties": {"title": cls.LOGS_TAB}},
            ]
        }
        res = service.spreadsheets().create(body=spreadsheet_body).execute()
        sheet_id = res.get("spreadsheetId")
        sheet_url = res.get("spreadsheetUrl")
        logger.info(f"✨ Created new Google Spreadsheet: {sheet_url}")

        # Write headers
        cls._spreadsheet_id = sheet_id
        cls._write_headers_if_missing(sheet_id)

        # Update .env file
        try:
            env_path = ".env"
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "GOOGLE_SHEET_ID=" in content:
                    import re
                    content = re.sub(r"GOOGLE_SHEET_ID=.*", f"GOOGLE_SHEET_ID={sheet_id}", content)
                else:
                    content += f"\n# Google Sheet Database ID\nGOOGLE_SHEET_ID={sheet_id}\n"
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception as e:
            logger.warning(f"Could not persist GOOGLE_SHEET_ID to .env: {e}")

        return sheet_id

    @classmethod
    def _write_headers_if_missing(cls, sheet_id: str):
        """Initializes header rows in all three tabs."""
        service = cls.get_service()
        tabs = [
            (cls.ASSIGNMENTS_TAB, cls.ASSIGNMENTS_HEADERS),
            (cls.SUBTASKS_TAB, cls.SUBTASKS_HEADERS),
            (cls.LOGS_TAB, cls.LOGS_HEADERS)
        ]
        for tab_name, headers in tabs:
            try:
                res = service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=f"'{tab_name}'!A1:Z1"
                ).execute()
                values = res.get("values", [])
                if not values or not values[0]:
                    service.spreadsheets().values().update(
                        spreadsheetId=sheet_id,
                        range=f"'{tab_name}'!A1",
                        valueInputOption="USER_ENTERED",
                        body={"values": [headers]}
                    ).execute()
            except Exception as e:
                logger.warning(f"Error initializing headers for tab '{tab_name}': {e}")

    @classmethod
    def init_database(cls, schema_path: str = ""):
        """Initializes Google Sheets database tabs and columns."""
        logger.info("Initializing Google Sheets database storage...")
        sheet_id = cls.get_spreadsheet_id()
        cls._write_headers_if_missing(sheet_id)
        logger.info(f"Google Sheets database ready. Sheet ID: {sheet_id}")

    @classmethod
    def _clear_cache(cls):
        """Clears cached sheet rows after writes."""
        cls._rows_cache.clear()

    @classmethod
    def _get_tab_rows(cls, tab_name: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Reads all rows from a tab and returns them as a list of dicts mapped to header keys."""
        import time
        now = time.time()
        if not force_refresh and tab_name in cls._rows_cache:
            cache_entry = cls._rows_cache[tab_name]
            if now - cache_entry["time"] < cls._cache_ttl:
                return [dict(r) for r in cache_entry["rows"]]

        service = cls.get_service()
        sheet_id = cls.get_spreadsheet_id()
        try:
            res = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=f"'{tab_name}'!A:Z"
            ).execute()
            raw_values = res.get("values", [])
            if not raw_values or len(raw_values) < 2:
                cls._rows_cache[tab_name] = {"time": now, "rows": []}
                return []
            headers = [h.strip() for h in raw_values[0]]
            rows = []
            for row_idx, row in enumerate(raw_values[1:], start=2):
                row_dict = {"_row_num": row_idx}
                for col_idx, header in enumerate(headers):
                    val = row[col_idx] if col_idx < len(row) else ""
                    row_dict[header] = val
                rows.append(row_dict)

            cls._rows_cache[tab_name] = {"time": now, "rows": rows}
            return rows
        except Exception as e:
            logger.error(f"Failed to read from Google Sheet '{tab_name}': {e}")
            return []

    @classmethod
    def log_execution(cls, action: str, status: str, retry_count: int = 0, details: Optional[str] = None, error_message: Optional[str] = None):
        """Records an execution event to ExecutionLogs sheet."""
        try:
            service = cls.get_service()
            sheet_id = cls.get_spreadsheet_id()
            row = [
                str(int(datetime.now().timestamp())),
                action,
                status,
                str(retry_count),
                details or "",
                error_message or "",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"'{cls.LOGS_TAB}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [row]}
            ).execute()
        except Exception as e:
            logger.warning(f"Could not log execution to Google Sheet: {e}")

    @classmethod
    def is_assignment_processed(cls, assignment_id: str) -> bool:
        """Checks if an assignment has already been processed in Google Sheets."""
        rows = cls._get_tab_rows(cls.ASSIGNMENTS_TAB)
        for r in rows:
            if str(r.get("id")) == str(assignment_id):
                return r.get("status") == "PROCESSED"
        return False

    @classmethod
    def save_assignment(cls, assignment_data: Dict[str, Any]):
        """Inserts or updates an assignment in Google Sheets."""
        service = cls.get_service()
        sheet_id = cls.get_spreadsheet_id()
        rows = cls._get_tab_rows(cls.ASSIGNMENTS_TAB)

        target_row_num = None
        for r in rows:
            if str(r.get("id")) == str(assignment_data.get("id")):
                target_row_num = r["_row_num"]
                break
        cls._clear_cache()

        row_values = [
            str(assignment_data.get("id") or ""),
            str(assignment_data.get("course_id") or ""),
            str(assignment_data.get("course_name") or ""),
            str(assignment_data.get("title") or ""),
            str(assignment_data.get("description") or ""),
            str(assignment_data.get("due_date") or ""),
            str(assignment_data.get("alternate_link") or ""),
            str(assignment_data.get("status") or "PENDING"),
            str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ]

        if target_row_num:
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{cls.ASSIGNMENTS_TAB}'!A{target_row_num}",
                valueInputOption="USER_ENTERED",
                body={"values": [row_values]}
            ).execute()
        else:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"'{cls.ASSIGNMENTS_TAB}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [row_values]}
            ).execute()
        cls._clear_cache()

    @classmethod
    def save_subtasks(cls, assignment_id: str, subtasks: List[Dict[str, Any]]):
        """Saves AI generated subtasks to Subtasks sheet and marks assignment as PROCESSED."""
        service = cls.get_service()
        sheet_id = cls.get_spreadsheet_id()

        # Read existing subtasks to keep non-matching ones
        all_subtasks = cls._get_tab_rows(cls.SUBTASKS_TAB)
        filtered_subtasks = [s for s in all_subtasks if str(s.get("assignment_id")) != str(assignment_id)]

        max_id = 0
        for s in all_subtasks:
            try:
                max_id = max(max_id, int(s.get("id", 0)))
            except Exception:
                pass

        new_rows = []
        for s in filtered_subtasks:
            new_rows.append([
                s.get("id", ""),
                s.get("assignment_id", ""),
                s.get("task_order", ""),
                s.get("task_title", ""),
                s.get("description", ""),
                s.get("priority", "MEDIUM"),
                s.get("estimated_hours", 1),
                s.get("suggested_start_date", ""),
                s.get("suggested_due_date", ""),
                s.get("status", "TODO")
            ])

        for idx, task in enumerate(subtasks, start=1):
            max_id += 1
            new_rows.append([
                str(max_id),
                str(assignment_id),
                str(task.get("task_order", idx)),
                str(task.get("task_title") or ""),
                str(task.get("description") or ""),
                str(task.get("priority", "MEDIUM")).upper(),
                str(task.get("estimated_hours", 1.0)),
                str(task.get("suggested_start_date") or ""),
                str(task.get("suggested_due_date") or ""),
                str(task.get("status", "TODO")).upper()
            ])

        # Rewrite Subtasks sheet
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"'{cls.SUBTASKS_TAB}'!A:Z"
        ).execute()

        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{cls.SUBTASKS_TAB}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [cls.SUBTASKS_HEADERS] + new_rows}
        ).execute()

        # Mark assignment as PROCESSED
        assignments = cls._get_tab_rows(cls.ASSIGNMENTS_TAB)
        for a in assignments:
            if str(a.get("id")) == str(assignment_id):
                row_idx = a["_row_num"]
                # Column H is status (index 8 = col H)
                service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=f"'{cls.ASSIGNMENTS_TAB}'!H{row_idx}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [["PROCESSED"]]}
                ).execute()
                break
        cls._clear_cache()

    @classmethod
    def get_assignment_with_subtasks(cls, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves assignment and matching subtasks from Google Sheets."""
        assignments = cls._get_tab_rows(cls.ASSIGNMENTS_TAB)
        target = None
        for a in assignments:
            if str(a.get("id")) == str(assignment_id):
                target = dict(a)
                break
        cls._clear_cache()

        if not target:
            return None

        subtasks = cls._get_tab_rows(cls.SUBTASKS_TAB)
        matched = []
        for s in subtasks:
            if str(s.get("assignment_id")) == str(assignment_id):
                s_copy = dict(s)
                # Ensure guaranteed id so frontend toggle and API never fail
                if not s_copy.get("id"):
                    s_copy["id"] = str(s.get("_row_num"))
                try:
                    s_copy["task_order"] = int(s_copy.get("task_order", 1))
                except Exception:
                    s_copy["task_order"] = 1
                try:
                    s_copy["estimated_hours"] = float(s_copy.get("estimated_hours", 1.0))
                except Exception:
                    s_copy["estimated_hours"] = 1.0
                matched.append(s_copy)

        matched.sort(key=lambda x: x.get("task_order", 0))
        target["subtasks"] = matched
        return target

    @classmethod
    def get_all_projects(cls) -> List[Dict[str, Any]]:
        """Retrieves all projects with computed subtask progress metrics."""
        assignments = cls._get_tab_rows(cls.ASSIGNMENTS_TAB)
        subtasks = cls._get_tab_rows(cls.SUBTASKS_TAB)

        projects = []
        for a in assignments:
            a_id = str(a.get("id"))
            matched_tasks = [s for s in subtasks if str(s.get("assignment_id")) == a_id]

            total = len(matched_tasks)
            completed = sum(1 for s in matched_tasks if s.get("status") == "DONE")
            in_progress = sum(1 for s in matched_tasks if s.get("status") == "IN_PROGRESS")
            todo = sum(1 for s in matched_tasks if s.get("status") == "TODO")
            
            hours = 0.0
            for s in matched_tasks:
                try:
                    hours += float(s.get("estimated_hours", 0) or 0)
                except Exception:
                    pass

            progress_percent = round((completed / total * 100), 1) if total > 0 else 0
            due_date = a.get("due_date", "")

            projects.append({
                "id": a_id,
                "course_id": a.get("course_id", ""),
                "course_name": a.get("course_name", ""),
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "due_date": due_date,
                "due_date_str": due_date if due_date else "No deadline",
                "alternate_link": a.get("alternate_link", ""),
                "status": a.get("status", "PENDING"),
                "total_tasks": total,
                "completed_tasks": completed,
                "in_progress_tasks": in_progress,
                "todo_tasks": todo,
                "total_estimated_hours": hours,
                "progress_percent": progress_percent
            })

        projects.reverse()  # Newest first
        return projects

    @classmethod
    def update_subtask_status(cls, subtask_id: Any, new_status: str) -> bool:
        """Updates subtask status in Google Sheets (TODO, IN_PROGRESS, DONE)."""
        if new_status not in ("TODO", "IN_PROGRESS", "DONE"):
            raise ValueError(f"Invalid status: {new_status}")

        service = cls.get_service()
        sheet_id = cls.get_spreadsheet_id()
        subtasks = cls._get_tab_rows(cls.SUBTASKS_TAB)

        target_row_idx = None
        query_id = str(subtask_id).strip()

        # 1. Exact match by subtask id
        for s in subtasks:
            s_id = str(s.get("id") or "").strip()
            if s_id and s_id == query_id:
                target_row_idx = s["_row_num"]
                break

        # 2. Match by direct sheet row index
        if target_row_idx is None:
            try:
                num = int(query_id)
                for s in subtasks:
                    if s.get("_row_num") == num:
                        target_row_idx = s["_row_num"]
                        break
            except Exception:
                pass

        # 3. Fallback: match by task_order if unique
        if target_row_idx is None:
            for s in subtasks:
                s_order = str(s.get("task_order") or "").strip()
                if s_order and s_order == query_id:
                    target_row_idx = s["_row_num"]
                    break

        if target_row_idx is not None:
            # Column J is status (10th column = J)
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{cls.SUBTASKS_TAB}'!J{target_row_idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [[new_status]]}
            ).execute()
            cls._clear_cache()
            logger.info(f"Updated subtask {subtask_id} (row {target_row_idx}) status to {new_status}")
            return True

        logger.warning(f"Could not find subtask with id/order '{subtask_id}' in Google Sheets.")
        return False

    @classmethod
    def get_today_focus_tasks(cls) -> List[Dict[str, Any]]:
        """Retrieves subtasks in progress or high priority due soon."""
        subtasks = cls._get_tab_rows(cls.SUBTASKS_TAB)
        assignments = {str(a.get("id")): a for a in cls._get_tab_rows(cls.ASSIGNMENTS_TAB)}

        focus = []
        for s in subtasks:
            status = s.get("status", "TODO")
            if status in ("TODO", "IN_PROGRESS"):
                parent = assignments.get(str(s.get("assignment_id")), {})
                due = s.get("suggested_due_date", "")
                focus.append({
                    "id": s.get("id"),
                    "assignment_id": s.get("assignment_id"),
                    "task_title": s.get("task_title"),
                    "description": s.get("description"),
                    "priority": s.get("priority", "MEDIUM"),
                    "estimated_hours": s.get("estimated_hours", 1),
                    "status": status,
                    "suggested_due_date": due,
                    "due_date_str": due if due else "-",
                    "assignment_title": parent.get("title", "Project"),
                    "course_name": parent.get("course_name", "")
                })

        # Sort: IN_PROGRESS first, then HIGH priority
        priority_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
        status_order = {"IN_PROGRESS": 1, "TODO": 2}
        focus.sort(key=lambda x: (
            status_order.get(x["status"], 2),
            priority_order.get(x.get("priority", "MEDIUM"), 2),
            x.get("suggested_due_date") or "9999"
        ))

        return focus[:8]

    @classmethod
    def get_upcoming_deadlines(cls) -> List[Dict[str, Any]]:
        """Retrieves upcoming assignments with deadlines."""
        projects = cls.get_all_projects()
        with_due = [p for p in projects if p.get("due_date")]
        with_due.sort(key=lambda x: x.get("due_date", "9999"))
        return with_due[:6]

    @classmethod
    def clear_all_data(cls) -> Dict[str, int]:
        """Clears all rows (except headers) from Assignments and Subtasks tabs."""
        service = cls.get_service()
        sheet_id = cls.get_spreadsheet_id()

        deleted = {"assignments": 0, "subtasks": 0}

        for tab_name, key in [(cls.ASSIGNMENTS_TAB, "assignments"), (cls.SUBTASKS_TAB, "subtasks")]:
            rows = cls._get_tab_rows(tab_name)
            deleted[key] = len(rows)
            if rows:
                # Clear all data rows (row 2 onward), keep header row 1
                service.spreadsheets().values().clear(
                    spreadsheetId=sheet_id,
                    range=f"'{tab_name}'!A2:Z10000",
                ).execute()

        cls._clear_cache()
        logger.info(f"Cleared all data: {deleted}")
        return deleted

    @classmethod
    def get_dashboard_metrics(cls) -> Dict[str, Any]:
        """Calculates aggregated dashboard metrics directly from Google Sheets."""
        assignments = cls._get_tab_rows(cls.ASSIGNMENTS_TAB)
        subtasks = cls._get_tab_rows(cls.SUBTASKS_TAB)

        total_assignments = len(assignments)
        total_subtasks = len(subtasks)
        done_subtasks = sum(1 for s in subtasks if s.get("status") == "DONE")
        in_progress_subtasks = sum(1 for s in subtasks if s.get("status") == "IN_PROGRESS")
        todo_subtasks = sum(1 for s in subtasks if s.get("status") == "TODO")

        total_hours = 0.0
        for s in subtasks:
            try:
                total_hours += float(s.get("estimated_hours", 0) or 0)
            except Exception:
                pass

        completion_rate = round((done_subtasks / total_subtasks * 100), 1) if total_subtasks > 0 else 0

        return {
            "total_assignments": total_assignments,
            "total_subtasks": total_subtasks,
            "done_subtasks": done_subtasks,
            "in_progress_subtasks": in_progress_subtasks,
            "todo_subtasks": todo_subtasks,
            "total_hours": total_hours,
            "completion_rate": completion_rate
        }

