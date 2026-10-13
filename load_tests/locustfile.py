import time
import random
from locust import HttpUser, task, between

class AssessmentCandidateUser(HttpUser):
    """
    Simulates a realistic candidate assessment lifecycle against CSL backend:
    1. Fetches colleges list (/api/assessment/colleges/)
    2. Registers candidate (/api/assessment/register/)
    3. Fetches eligible assessments (/api/assessment/candidate-assessments/)
    4. Starts/resumes attempt (/api/assessment/start/)
    5. Periodically saves answers (/api/assessment/attempts/{id}/answer/)
    6. Periodically records benign integrity events (/api/assessment/attempts/{id}/integrity-event/)
    7. Finalizes attempt (/api/assessment/attempts/{id}/finalize/)
    """
    wait_time = between(2, 4)

    def on_start(self):
        self.timestamp = int(time.time() * 1000)
        self.candidate_email = f"locust_{self.timestamp}_{random.randint(1000, 9999)}@testcsl.edu"
        self.token = None
        self.attempt_id = None
        self.questions = []
        self.headers = {"Content-Type": "application/json"}
        self.prepare_candidate_session()

    def prepare_candidate_session(self):
        # 1. Fetch colleges
        colleges_resp = self.client.get("/api/assessment/colleges/", name="/api/assessment/colleges/")
        college_id = None
        college_name = "CSL Testing Institute"
        if colleges_resp.status_code == 200:
            try:
                colleges = colleges_resp.json()
                if isinstance(colleges, list) and len(colleges) > 0:
                    c = random.choice(colleges)
                    college_id = c.get("id")
                    college_name = c.get("name")
            except Exception:
                pass

        # 2. Register Candidate
        reg_payload = {
            "full_name": f"Candidate {random.randint(100, 999)}",
            "email": self.candidate_email,
            "phone_number": f"9{random.randint(100000000, 999999999)}",
            "register_number": f"REG{random.randint(100000, 999999)}",
            "department": "Computer Science",
            "year_of_study": "Final Year",
            "college_id": college_id,
            "college": college_name,
        }
        reg_resp = self.client.post("/api/assessment/register/", json=reg_payload, name="/api/assessment/register/")
        if reg_resp.status_code not in (200, 201):
            return

        reg_data = reg_resp.json()
        self.token = reg_data.get("assessment_token")
        if not self.token:
            return

        self.headers["Authorization"] = f"Bearer {self.token}"
        self.headers["X-Assessment-Token"] = self.token

        # 3. Check eligible assessments
        elig_resp = self.client.get("/api/assessment/candidate-assessments/", headers=self.headers, name="/api/assessment/candidate-assessments/")
        assessment_id = None
        if elig_resp.status_code == 200:
            try:
                elig_data = elig_resp.json()
                assessments = elig_data.get("assessments", [])
                open_assessments = [a for a in assessments if a.get("is_open") and a.get("user_can_attempt")]
                if open_assessments:
                    assessment_id = open_assessments[0].get("id")
            except Exception:
                pass

        # 4. Start Assessment
        start_payload = {"assessment_id": assessment_id} if assessment_id else {}
        start_resp = self.client.post("/api/assessment/start/", json=start_payload, headers=self.headers, name="/api/assessment/start/")
        if start_resp.status_code == 200:
            start_data = start_resp.json()
            self.attempt_id = start_data.get("id")
            new_token = start_data.get("assessment_token")
            if new_token:
                self.token = new_token
                self.headers["Authorization"] = f"Bearer {new_token}"
                self.headers["X-Assessment-Token"] = new_token
            self.questions = start_data.get("questions", [])

    @task(6)
    def save_random_answer(self):
        if not self.attempt_id or not self.questions:
            return
        q = random.choice(self.questions)
        q_order = q.get("question_order", 1)
        sel_opt = random.choice(["A", "B", "C", "D"])
        self.client.post(
            f"/api/assessment/attempts/{self.attempt_id}/answer/",
            json={"question_order": q_order, "selected_option": sel_opt},
            headers=self.headers,
            name="/api/assessment/attempts/:id/answer/"
        )

    @task(2)
    def record_benign_integrity_event(self):
        if not self.attempt_id:
            return
        self.client.post(
            f"/api/assessment/attempts/{self.attempt_id}/integrity-event/",
            json={
                "event_type": "TAB_VISIBLE",
                "event_id": f"locust-evt-{random.randint(10000, 99999)}",
                "metadata": {}
            },
            headers=self.headers,
            name="/api/assessment/attempts/:id/integrity-event/"
        )

    @task(1)
    def finalize_session(self):
        if not self.attempt_id:
            return
        self.client.post(
            f"/api/assessment/attempts/{self.attempt_id}/finalize/",
            json={},
            headers=self.headers,
            name="/api/assessment/attempts/:id/finalize/"
        )
