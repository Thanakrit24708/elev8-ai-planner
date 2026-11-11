import os
from datetime import datetime
from typing import List, Dict, Any, Optional

# Allow OAuthLib to accept Google scope aliases/modifications without raising ScopeChanged error
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import Config
from src.utils.logger import logger
from src.utils.retry import retry_api_call

class ClassroomService:
    """Service to authenticate with Google Classroom API and fetch course assignments."""

    def __init__(self):
        self.creds: Optional[Credentials] = None
        self.service = None

    def authenticate(self) -> bool:
        """
        Authenticates via OAuth 2.0.
        Loads existing token from token.json or triggers interactive browser login using credentials.json.
        """
        token_path = Config.GOOGLE_TOKEN_FILE
        credentials_path = Config.GOOGLE_CLIENT_SECRETS_FILE

        if os.path.exists(token_path):
            try:
                self.creds = Credentials.from_authorized_user_file(token_path, Config.CLASSROOM_SCOPES)
                if not self.creds.has_scopes(Config.CLASSROOM_SCOPES):
                    logger.info("Existing credentials missing new scopes (e.g. Spreadsheets). Will re-authenticate.")
                    self.creds = None
                else:
                    logger.info("Loaded existing Google OAuth credentials from token file.")
            except Exception as e:
                logger.warning(f"Failed to load token file: {e}. Will re-authenticate.")
                self.creds = None

        # If there are no valid credentials available, request login
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing expired Google OAuth access token...")
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Could not refresh token: {e}. Launching interactive flow.")
                    self.creds = None

            if not self.creds:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Google OAuth credentials file '{credentials_path}' not found! "
                        f"Please download your client_secret JSON from Google Cloud Console "
                        f"and place it at '{credentials_path}'."
                    )

                logger.info("Launching OAuth 2.0 desktop authentication flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, Config.CLASSROOM_SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # Save the credentials for subsequent runs
            with open(token_path, "w", encoding="utf-8") as token_file:
                token_file.write(self.creds.to_json())
            logger.info(f"OAuth credentials successfully saved to '{token_path}'.")

        self.service = build("classroom", "v1", credentials=self.creds)
        return True

    @staticmethod
    def _parse_due_date(due_date_obj: Optional[Dict], due_time_obj: Optional[Dict]) -> Optional[str]:
        """Converts Classroom API dueDate and dueTime dictionaries to SQL datetime string."""
        if not due_date_obj:
            return None
        year = due_date_obj.get("year", 1970)
        month = due_date_obj.get("month", 1)
        day = due_date_obj.get("day", 1)

        hours = 23
        minutes = 59
        if due_time_obj:
            hours = due_time_obj.get("hours", 23)
            minutes = due_time_obj.get("minutes", 59)

        try:
            dt = datetime(year, month, day, hours, minutes)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @retry_api_call(action_name="CLASSROOM_FETCH_COURSES")
    def _get_courses(self) -> List[Dict[str, Any]]:
        """Fetches list of active courses with retry logic."""
        results = self.service.courses().list(pageSize=50, courseStates=["ACTIVE"]).execute()
        return results.get("courses", [])

    @retry_api_call(action_name="CLASSROOM_FETCH_COURSEWORK")
    def _get_course_work(self, course_id: str) -> List[Dict[str, Any]]:
        """Fetches coursework for a specific course with retry logic."""
        results = self.service.courses().courseWork().list(
            courseId=course_id,
            pageSize=50,
            courseWorkStates=["PUBLISHED"]
        ).execute()
        return results.get("courseWork", [])

    def fetch_all_assignments(self) -> List[Dict[str, Any]]:
        """
        Fetches all published assignments across configured or active courses.
        Returns a normalized list of assignment dictionaries.
        """
        if not self.service:
            self.authenticate()

        assignments: List[Dict[str, Any]] = []
        courses = self._get_courses()

        target_course_ids = set(Config.CLASSROOM_COURSE_IDS)

        for course in courses:
            course_id = course.get("id")
            course_name = course.get("name", "Unnamed Course")

            # Filter if specific course IDs are configured
            if target_course_ids and course_id not in target_course_ids:
                continue

            logger.info(f"Scanning assignments for course: {course_name} (ID: {course_id})")

            try:
                course_works = self._get_course_work(course_id)
                for cw in course_works:
                    work_id = cw.get("id")
                    title = cw.get("title", "Untitled Assignment")
                    description = cw.get("description", "")
                    due_date = self._parse_due_date(cw.get("dueDate"), cw.get("dueTime"))
                    alternate_link = cw.get("alternateLink", "")

                    assignments.append({
                        "id": work_id,
                        "course_id": course_id,
                        "course_name": course_name,
                        "title": title,
                        "description": description,
                        "due_date": due_date,
                        "alternate_link": alternate_link,
                        "status": "PENDING",
                        "raw_json": cw
                    })
            except HttpError as err:
                logger.error(f"Error fetching coursework for course {course_id}: {err}")
                continue

        logger.info(f"Total assignments retrieved from Google Classroom: {len(assignments)}")
        return assignments
