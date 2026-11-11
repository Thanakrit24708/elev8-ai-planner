import json
import pymysql
import pymysql.cursors
from typing import Dict, Any, List, Optional
from src.config import Config
from src.utils.logger import logger

class DatabaseService:
    """Service to handle MariaDB operations for assignments, subtasks, and execution logs."""

    @staticmethod
    def get_connection(include_database: bool = True):
        """Creates and returns a new connection to MariaDB."""
        return pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME if include_database else None,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )

    @classmethod
    def init_database(cls, schema_path: str = "database/schema.sql"):
        """Initializes database schema from SQL file if not already created."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.init_database(schema_path)

        logger.info(f"Initializing database '{Config.DB_NAME}' from {schema_path}...")
        try:
            # First connect without database selected to create database if needed
            conn = cls.get_connection(include_database=False)
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            conn.commit()
            conn.close()

            # Now connect to the database and run table creation statements
            conn = cls.get_connection(include_database=True)
            with conn.cursor() as cursor:
                with open(schema_path, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                # Split queries by semicolon to execute individually
                statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]
                for statement in statements:
                    cursor.execute(statement)

            conn.commit()
            conn.close()
            logger.info("Database schema initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise e

    @classmethod
    def log_execution(
        cls,
        action: str,
        status: str,
        retry_count: int = 0,
        details: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Records an execution event or error into execution_logs table."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.log_execution(action, status, retry_count, details, error_message)

        try:
            conn = cls.get_connection(include_database=True)
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO execution_logs (action, status, retry_count, details, error_message)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (action, status, retry_count, details, error_message))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not record execution log to DB: {e}")

    @classmethod
    def is_assignment_processed(cls, assignment_id: str) -> bool:
        """Checks if an assignment has already been processed or stored."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.is_assignment_processed(assignment_id)

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT status FROM assignments WHERE id = %s", (assignment_id,))
                result = cursor.fetchone()
                return result is not None and result["status"] == "PROCESSED"
        finally:
            conn.close()

    @classmethod
    def save_assignment(cls, assignment_data: Dict[str, Any]):
        """Inserts or updates an assignment in the database."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.save_assignment(assignment_data)

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO assignments (
                        id, course_id, course_name, title, description, due_date, alternate_link, status, raw_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        course_name = VALUES(course_name),
                        title = VALUES(title),
                        description = VALUES(description),
                        due_date = VALUES(due_date),
                        alternate_link = VALUES(alternate_link),
                        raw_json = VALUES(raw_json)
                """
                raw_json = json.dumps(assignment_data.get("raw_json", {}), ensure_ascii=False)
                cursor.execute(sql, (
                    assignment_data.get("id"),
                    assignment_data.get("course_id"),
                    assignment_data.get("course_name"),
                    assignment_data.get("title"),
                    assignment_data.get("description"),
                    assignment_data.get("due_date"),
                    assignment_data.get("alternate_link"),
                    assignment_data.get("status", "PENDING"),
                    raw_json
                ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save assignment {assignment_data.get('id')}: {e}")
            raise e
        finally:
            conn.close()

    @classmethod
    def save_subtasks(cls, assignment_id: str, subtasks: List[Dict[str, Any]]):
        """Saves AI generated subtasks for a specific assignment within a transaction."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.save_subtasks(assignment_id, subtasks)

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                # Remove existing subtasks for this assignment if re-analyzing
                cursor.execute("DELETE FROM subtasks WHERE assignment_id = %s", (assignment_id,))

                insert_sql = """
                    INSERT INTO subtasks (
                        assignment_id, task_order, task_title, description, priority,
                        estimated_hours, suggested_start_date, suggested_due_date, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                for idx, task in enumerate(subtasks, start=1):
                    cursor.execute(insert_sql, (
                        assignment_id,
                        task.get("task_order", idx),
                        task.get("task_title"),
                        task.get("description", ""),
                        task.get("priority", "MEDIUM").upper(),
                        task.get("estimated_hours", 1.0),
                        task.get("suggested_start_date"),
                        task.get("suggested_due_date"),
                        task.get("status", "TODO")
                    ))

                # Update assignment status to PROCESSED
                cursor.execute(
                    "UPDATE assignments SET status = 'PROCESSED' WHERE id = %s",
                    (assignment_id,)
                )

            conn.commit()
            logger.info(f"Saved {len(subtasks)} subtasks for assignment {assignment_id}.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save subtasks for assignment {assignment_id}: {e}")
            # Mark assignment as FAILED
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE assignments SET status = 'FAILED' WHERE id = %s", (assignment_id,))
                conn.commit()
            except Exception:
                pass
            raise e
        finally:
            conn.close()

    @classmethod
    def get_assignment_with_subtasks(cls, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an assignment and its associated subtasks."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.get_assignment_with_subtasks(assignment_id)

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
                assignment = cursor.fetchone()
                if not assignment:
                    return None

                cursor.execute(
                    "SELECT * FROM subtasks WHERE assignment_id = %s ORDER BY task_order ASC",
                    (assignment_id,)
                )
                assignment["subtasks"] = cursor.fetchall()
                return assignment
        finally:
            conn.close()

    @classmethod
    def get_all_projects(cls) -> List[Dict[str, Any]]:
        """Phase 4: Retrieves all projects with aggregated subtask progress metrics."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.get_all_projects()

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        a.id, a.course_id, a.course_name, a.title, a.description,
                        a.due_date, a.alternate_link, a.status, a.created_at,
                        COUNT(s.id) AS total_tasks,
                        SUM(CASE WHEN s.status = 'DONE' THEN 1 ELSE 0 END) AS completed_tasks,
                        SUM(CASE WHEN s.status = 'IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress_tasks,
                        SUM(CASE WHEN s.status = 'TODO' THEN 1 ELSE 0 END) AS todo_tasks,
                        COALESCE(SUM(s.estimated_hours), 0) AS total_estimated_hours
                    FROM assignments a
                    LEFT JOIN subtasks s ON a.id = s.assignment_id
                    GROUP BY a.id
                    ORDER BY a.created_at DESC
                """
                cursor.execute(sql)
                projects = cursor.fetchall()

                for p in projects:
                    total = p["total_tasks"]
                    done = p["completed_tasks"]
                    p["progress_percent"] = round((done / total * 100), 1) if total > 0 else 0
                    if p["due_date"]:
                        p["due_date_str"] = p["due_date"].strftime("%Y-%m-%d %H:%M")
                    else:
                        p["due_date_str"] = "No deadline"

                return projects
        finally:
            conn.close()

    @classmethod
    def update_subtask_status(cls, subtask_id: int, new_status: str) -> bool:
        """Phase 4: Updates status of a subtask (TODO, IN_PROGRESS, DONE) in real-time."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.update_subtask_status(subtask_id, new_status)

        if new_status not in ("TODO", "IN_PROGRESS", "DONE"):
            raise ValueError(f"Invalid status: {new_status}")

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE subtasks SET status = %s WHERE id = %s",
                    (new_status, subtask_id)
                )
            conn.commit()
            return True
        finally:
            conn.close()

    @classmethod
    def get_today_focus_tasks(cls) -> List[Dict[str, Any]]:
        """Phase 4: Retrieves subtasks in progress or with high priority due soon."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.get_today_focus_tasks()

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        s.*, a.title AS assignment_title, a.course_name
                    FROM subtasks s
                    JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.status IN ('TODO', 'IN_PROGRESS')
                    ORDER BY 
                        CASE s.status WHEN 'IN_PROGRESS' THEN 1 ELSE 2 END,
                        CASE s.priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
                        s.suggested_due_date ASC
                    LIMIT 8
                """
                cursor.execute(sql)
                tasks = cursor.fetchall()
                for t in tasks:
                    if t.get("suggested_due_date"):
                        t["due_date_str"] = t["suggested_due_date"].strftime("%d %b %H:%M")
                    else:
                        t["due_date_str"] = "-"
                return tasks
        finally:
            conn.close()

    @classmethod
    def get_upcoming_deadlines(cls) -> List[Dict[str, Any]]:
        """Phase 4: Retrieves assignments with upcoming deadlines."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.get_upcoming_deadlines()

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        a.id, a.title, a.course_name, a.due_date, a.status,
                        COUNT(s.id) AS total_tasks,
                        SUM(CASE WHEN s.status = 'DONE' THEN 1 ELSE 0 END) AS completed_tasks
                    FROM assignments a
                    LEFT JOIN subtasks s ON a.id = s.assignment_id
                    WHERE a.due_date IS NOT NULL
                    GROUP BY a.id
                    ORDER BY a.due_date ASC
                    LIMIT 6
                """
                cursor.execute(sql)
                items = cursor.fetchall()
                for item in items:
                    if item.get("due_date"):
                        item["due_date_str"] = item["due_date"].strftime("%d %b %Y %H:%M")
                    else:
                        item["due_date_str"] = "Not specified"
                return items
        finally:
            conn.close()

    @classmethod
    def get_dashboard_metrics(cls) -> Dict[str, Any]:
        """Phase 4: Aggregated overall dashboard statistics."""
        if Config.STORAGE_ENGINE == "sheets":
            from src.services.sheet_service import SheetService
            return SheetService.get_dashboard_metrics()

        conn = cls.get_connection(include_database=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total_assignments FROM assignments")
                total_assignments = cursor.fetchone()["total_assignments"]

                cursor.execute("""
                    SELECT 
                        COUNT(*) AS total_subtasks,
                        SUM(CASE WHEN status = 'DONE' THEN 1 ELSE 0 END) AS done_subtasks,
                        SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress_subtasks,
                        SUM(CASE WHEN status = 'TODO' THEN 1 ELSE 0 END) AS todo_subtasks,
                        COALESCE(SUM(estimated_hours), 0) AS total_hours
                    FROM subtasks
                """)
                subtask_stats = cursor.fetchone()

                total_st = subtask_stats["total_subtasks"] or 0
                done_st = subtask_stats["done_subtasks"] or 0
                completion_rate = round((done_st / total_st * 100), 1) if total_st > 0 else 0

                return {
                    "total_assignments": total_assignments,
                    "total_subtasks": total_st,
                    "done_subtasks": done_st,
                    "in_progress_subtasks": subtask_stats["in_progress_subtasks"] or 0,
                    "todo_subtasks": subtask_stats["todo_subtasks"] or 0,
                    "total_hours": float(subtask_stats["total_hours"] or 0),
                    "completion_rate": completion_rate
                }
        finally:
            conn.close()
