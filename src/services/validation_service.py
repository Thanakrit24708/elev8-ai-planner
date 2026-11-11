from typing import Dict, Any, List, Tuple
from datetime import datetime
from src.utils.logger import logger

class ValidationService:
    """
    Phase 2: Automated Validation Loop Tool
    Performs 3-point automated validation:
    1. Completeness (ความครบถ้วน)
    2. Logic Flow & Dependencies (ความสมเหตุสมผลของกระบวนการ)
    3. Timeline Limit (กรอบระยะเวลา)
    """

    @classmethod
    def validate_plan(
        cls,
        assignment: Dict[str, Any],
        subtasks: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validates the decomposed subtasks against project constraints.
        Returns:
            is_valid (bool): True if all checks pass, False otherwise.
            feedbacks (List[str]): List of issues found for the AI to rectify.
            report (Dict[str, Any]): Detailed status of each validation dimension.
        """
        feedbacks: List[str] = []
        report = {
            "completeness": {"passed": True, "details": []},
            "logic_flow": {"passed": True, "details": []},
            "timeline": {"passed": True, "details": []}
        }

        # --- 1. Completeness Check (ความครบถ้วน) ---
        if not subtasks or len(subtasks) < 3:
            msg = f"Task decomposition is too brief ({len(subtasks)} tasks). Need at least 3 distinct subtasks covering research, implementation, and review."
            feedbacks.append(msg)
            report["completeness"]["passed"] = False
            report["completeness"]["details"].append(msg)

        for idx, task in enumerate(subtasks, start=1):
            title = task.get("task_title", "").strip()
            desc = task.get("description", "").strip()
            if not title or len(title) < 4:
                msg = f"Task #{idx} has an unclear or missing title."
                feedbacks.append(msg)
                report["completeness"]["passed"] = False
                report["completeness"]["details"].append(msg)
            if not desc:
                msg = f"Task #{idx} ('{title}') lacks a description of actionable steps."
                feedbacks.append(msg)
                report["completeness"]["passed"] = False
                report["completeness"]["details"].append(msg)

        # --- 2. Logic Flow Check (ความสมเหตุสมผลของกระบวนการ) ---
        orders = [t.get("task_order", i + 1) for i, t in enumerate(subtasks)]
        if sorted(orders) != list(range(1, len(subtasks) + 1)):
            msg = "Task orders are inconsistent or not strictly sequential starting from 1."
            feedbacks.append(msg)
            report["logic_flow"]["passed"] = False
            report["logic_flow"]["details"].append(msg)

        # Check chronology of dates
        parsed_dates = []
        for idx, task in enumerate(subtasks, start=1):
            due_str = task.get("suggested_due_date")
            if due_str:
                try:
                    dt = datetime.strptime(due_str, "%Y-%m-%d %H:%M:%S")
                    parsed_dates.append((idx, dt))
                except Exception:
                    try:
                        dt = datetime.strptime(due_str, "%Y-%m-%d")
                        parsed_dates.append((idx, dt))
                    except Exception:
                        pass

        # Check if dates move forward
        for i in range(len(parsed_dates) - 1):
            curr_idx, curr_dt = parsed_dates[i]
            next_idx, next_dt = parsed_dates[i + 1]
            if next_dt < curr_dt:
                msg = f"Logic flow conflict: Task #{next_idx} is scheduled ({next_dt}) before Task #{curr_idx} ({curr_dt})."
                feedbacks.append(msg)
                report["logic_flow"]["passed"] = False
                report["logic_flow"]["details"].append(msg)

        # --- 3. Timeline Limit Check (กรอบระยะเวลา) ---
        final_due_str = assignment.get("due_date")
        if final_due_str:
            try:
                final_dt = datetime.strptime(final_due_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    final_dt = datetime.strptime(final_due_str, "%Y-%m-%d")
                except Exception:
                    final_dt = None

            if final_dt:
                for idx, task in enumerate(subtasks, start=1):
                    due_str = task.get("suggested_due_date")
                    if due_str:
                        try:
                            task_dt = datetime.strptime(due_str, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            try:
                                task_dt = datetime.strptime(due_str, "%Y-%m-%d")
                            except Exception:
                                task_dt = None

                        if task_dt and task_dt > final_dt:
                            msg = f"Timeline violation: Task #{idx} suggested due date ({task_dt}) exceeds final assignment deadline ({final_dt})."
                            feedbacks.append(msg)
                            report["timeline"]["passed"] = False
                            report["timeline"]["details"].append(msg)

        # Total hours sanity check
        total_hours = sum(float(t.get("estimated_hours", 1.0)) for t in subtasks)
        if total_hours <= 0:
            msg = "Total estimated hours must be greater than 0."
            feedbacks.append(msg)
            report["timeline"]["passed"] = False
            report["timeline"]["details"].append(msg)

        is_valid = len(feedbacks) == 0
        return is_valid, feedbacks, report

