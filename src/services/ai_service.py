import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ValidationError

from src.config import Config
from src.utils.logger import logger
from src.utils.retry import retry_api_call
from src.services.db_service import DatabaseService

# Pydantic schemas for strict validation
class SubTaskModel(BaseModel):
    task_order: int = Field(description="Order of execution starting from 1")
    task_title: str = Field(description="Clear, actionable title for this subtask")
    description: str = Field(description="Detailed explanation of what needs to be done")
    priority: str = Field(description="Priority level: HIGH, MEDIUM, or LOW")
    estimated_hours: float = Field(default=1.0, description="Estimated hours to complete")
    suggested_start_date: Optional[str] = Field(default=None, description="Suggested start date YYYY-MM-DD HH:MM:SS")
    suggested_due_date: Optional[str] = Field(default=None, description="Suggested finish date YYYY-MM-DD HH:MM:SS")

class ProjectPlanModel(BaseModel):
    project_summary: str = Field(description="High-level summary of the assignment and approach")
    subtasks: List[SubTaskModel] = Field(description="Sequential list of decomposed subtasks")


class AIService:
    """Service to decompose assignments into prioritized subtasks using Chat API."""

    def __init__(self):
        if not Config.AI_API_KEY:
            logger.warning("AI_API_KEY is not configured in .env file.")

    @staticmethod
    def _clean_json_response(content: str) -> str:
        """Strips markdown code fences (e.g. ```json ... ```) to extract raw JSON string."""
        content = content.strip()
        # Match ```json ... ``` or ``` ... ```
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()
        return content

    def _build_prompt(self, assignment: Dict[str, Any]) -> str:
        """Constructs an explicit system/user prompt enforcing strict JSON decomposition."""
        title = assignment.get("title", "")
        description = assignment.get("description", "") or "No description provided."
        due_date = assignment.get("due_date") or "No deadline specified (assume 7 days from now)."
        course_name = assignment.get("course_name", "General Course")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prompt = f"""
You are an expert Project Manager and Academic Coach. Your job is to break down this student assignment into an actionable, prioritized execution plan.

[ASSIGNMENT DETAILS]
Course: {course_name}
Title: {title}
Description: {description}
Final Due Date: {due_date}
Current Time: {current_time}

[INSTRUCTIONS]
1. Deconstruct this assignment into 3 to 7 logical, chronological subtasks (e.g., Research, Outline/Design, Implementation/Drafting, Review/Testing, Final Submission).
2. Assign each task a priority: "HIGH", "MEDIUM", or "LOW" based on dependency and effort.
3. Provide realistic estimated hours for each subtask.
4. Calculate realistic 'suggested_start_date' and 'suggested_due_date' (format: "YYYY-MM-DD HH:MM:SS") ensuring all subtasks complete comfortably before the final due date.
5. You MUST reply ONLY with a valid, parseable JSON object. Do not include any greeting, preamble, or commentary outside the JSON.
6. **IMPORTANT**: All text fields (project_summary, task_title, description) MUST be written in Thai language (ภาษาไทย). Use clear, natural Thai that a university student would understand.

[JSON OUTPUT SCHEMA]
{{
  "project_summary": "สรุปโปรเจกต์สั้นๆ 2-3 ประโยค เป็นภาษาไทย",
  "subtasks": [
    {{
      "task_order": 1,
      "task_title": "ชื่องานย่อยเป็นภาษาไทย",
      "description": "รายละเอียดขั้นตอนที่ต้องทำเป็นภาษาไทย",
      "priority": "HIGH",
      "estimated_hours": 2.5,
      "suggested_start_date": "YYYY-MM-DD HH:MM:SS",
      "suggested_due_date": "YYYY-MM-DD HH:MM:SS"
    }}
  ]
}}
"""
        return prompt.strip()

    @retry_api_call(action_name="AI_CHAT_COMPLETION")
    def _call_gemini_api(self, prompt: str) -> str:
        """Calls Google Gemini API using google-genai SDK or direct REST."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=Config.AI_API_KEY)
            response = client.models.generate_content(
                model=Config.AI_MODEL or "gemini-1.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            return response.text
        except ImportError:
            # Fallback to direct REST API if google-genai is not installed
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.AI_MODEL or 'gemini-1.5-flash'}:generateContent?key={Config.AI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2
                }
            }
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    @retry_api_call(action_name="AI_OPENAI_COMPATIBLE_API")
    def _call_openai_compatible_api(self, prompt: str) -> str:
        """Calls OpenAI-compatible / custom Chat API endpoint."""
        import requests
        base_url = Config.AI_BASE_URL.rstrip("/") if Config.AI_BASE_URL else "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {Config.AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": Config.AI_MODEL or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a project planning AI that outputs strict JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def analyze_assignment(self, assignment: Dict[str, Any]) -> ProjectPlanModel:
        """
        Submits assignment to AI Chat API with retries, validates and parses JSON response.
        """
        if not Config.AI_API_KEY:
            raise ValueError("AI_API_KEY is not set. Please update your .env file.")

        prompt = self._build_prompt(assignment)
        assignment_id = assignment.get("id", "UNKNOWN")
        logger.info(f"Submitting assignment '{assignment.get('title')}' (ID: {assignment_id}) to AI...")

        raw_response = ""
        try:
            if Config.AI_PROVIDER == "openai" or bool(Config.AI_BASE_URL):
                raw_response = self._call_openai_compatible_api(prompt)
            else:
                raw_response = self._call_gemini_api(prompt)

            clean_json = self._clean_json_response(raw_response)
            parsed_data = json.loads(clean_json)

            # Validate against Pydantic schema
            plan = ProjectPlanModel(**parsed_data)
            logger.info(f"Successfully generated {len(plan.subtasks)} subtasks for assignment {assignment_id}.")

            DatabaseService.log_execution(
                action="AI_PLANNING",
                status="SUCCESS",
                details=f"Generated {len(plan.subtasks)} subtasks for {assignment.get('title')}"
            )
            return plan

        except Exception as e:
            logger.error(f"Failed to generate project plan for assignment {assignment_id}: {e}")
            DatabaseService.log_execution(
                action="AI_PLANNING",
                status="FAILED",
                details=f"Assignment: {assignment.get('title')} ({assignment_id})",
                error_message=str(e)
            )
            raise e

    def analyze_assignment_with_validation_loop(
        self,
        assignment: Dict[str, Any],
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Phase 1 & Phase 2: AI Planning with Automated Validation Loop
        Iterates up to max_iterations if the Validation Tool detects flaws.
        """
        from src.services.validation_service import ValidationService

        iteration = 1
        feedbacks: List[str] = []
        last_plan = None
        last_report = None
        iteration_history = []

        while iteration <= max_iterations:
            logger.info(f"[VALIDATION LOOP] Iteration {iteration}/{max_iterations} for '{assignment.get('title')}'")

            # Build or refine prompt with feedbacks
            if iteration == 1:
                prompt = self._build_prompt(assignment)
            else:
                feedback_text = "\n".join([f"- {fb}" for fb in feedbacks])
                prompt = self._build_prompt(assignment) + f"""

[VALIDATION FEEDBACK FROM PREVIOUS ATTEMPT]
Your previous breakdown had the following issues that MUST be corrected:
{feedback_text}

Please rectify these issues and generate the corrected JSON plan.
"""

            raw_response = ""
            if Config.AI_PROVIDER == "openai" or bool(Config.AI_BASE_URL):
                raw_response = self._call_openai_compatible_api(prompt)
            else:
                raw_response = self._call_gemini_api(prompt)

            clean_json = self._clean_json_response(raw_response)
            parsed_data = json.loads(clean_json)
            plan = ProjectPlanModel(**parsed_data)
            last_plan = plan

            subtasks_dict = [t.model_dump() for t in plan.subtasks]
            is_valid, feedbacks, report = ValidationService.validate_plan(assignment, subtasks_dict)
            last_report = report

            iteration_history.append({
                "iteration": iteration,
                "is_valid": is_valid,
                "feedbacks": list(feedbacks),
                "report": report
            })

            if is_valid:
                logger.info(f"[VALIDATION LOOP] Passed all checks on iteration {iteration}!")
                break
            else:
                logger.warning(f"[VALIDATION LOOP] Iteration {iteration} failed validation: {feedbacks}")
                iteration += 1

        is_passed = (last_report is not None and len(feedbacks) == 0)
        return {
            "passed": is_passed,
            "iterations_used": min(iteration, max_iterations),
            "max_iterations": max_iterations,
            "plan": last_plan.model_dump() if last_plan else None,
            "feedbacks": feedbacks,
            "report": last_report,
            "history": iteration_history,
            "needs_manual_review": not is_passed
        }

    def generate_daily_briefing(self, pending_tasks: List[Dict[str, Any]]) -> str:
        """
        Phase 4: Generates a short, encouraging AI daily briefing for the student.
        """
        if not pending_tasks:
            return "ยอดเยี่ยมมาก! ไม่มีงานค้างในวันนี้ คุณสามารถพักผ่อนหรือศึกษาค้นคว้าเพิ่มเติมได้ตามอัธยาศัย 🎉"

        summary_tasks = []
        for t in pending_tasks[:5]:
            summary_tasks.append(f"- {t.get('task_title')} (วิชา: {t.get('course_name', 'ทั่วไป')}, ความสำคัญ: {t.get('priority')}, กำหนดส่ง: {t.get('suggested_due_date', 'เร็วๆ นี้')})")
        tasks_text = "\n".join(summary_tasks)

        prompt = f"""
คุณคือ AI Academic Coach ผู้ช่วยส่วนตัวของนักศึกษา
นี่คือรายการงานย่อยที่นักศึกษาต้องทำหรือควรโฟกัสในวันนี้:
{tasks_text}

จงเขียนข้อความ "AI Daily Briefing" สั้นๆ ไม่เกิน 3-4 ประโยค เป็นภาษาไทย
เนื้อหาต้องประกอบด้วย:
1. ทักทายอย่างกระตือรือร้นและให้กำลังใจ
2. ชี้เป้าว่างานไหนสำคัญที่สุดที่ควรเริ่มทำก่อน
3. คำแนะนำในการแบ่งเวลา
ตอบเป็นข้อความธรรมดา ไม่ต้องมีหัวข้อหรือคำนำ
"""
        try:
            if Config.AI_PROVIDER == "openai" or bool(Config.AI_BASE_URL):
                briefing = self._call_openai_compatible_api(prompt)
            else:
                briefing = self._call_gemini_api(prompt)
            return briefing.strip()
        except Exception as e:
            logger.warning(f"Failed to generate AI daily briefing: {e}")
            return f"วันนี้มีงานที่ต้องโฟกัส {len(pending_tasks)} งาน ขอแนะนำให้เริ่มจากงานที่มีความสำคัญสูงก่อนเพื่อรักษาเวลาส่งให้ตรงกำหนดครับ สู้ๆ!"
