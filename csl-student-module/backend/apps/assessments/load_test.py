"""
Simulated High-Concurrency Load Test for CSL Initial Assessment.
Tests 100 simultaneous candidates registering, starting assessment, answering questions, and submitting bursts.
Uses ThreadPoolExecutor to simulate concurrent student requests against the Django test client / database.
"""

import time
import concurrent.futures
from django.test import TransactionTestCase, Client
from apps.assessments.models import QuestionBank, AssessmentConfig, Candidate, AssessmentAttempt


class ConcurrencyLoadTest(TransactionTestCase):
    def setUp(self):
        self.config = AssessmentConfig.objects.create(
            title="CSL Initial Assessment",
            duration_minutes=60,
            total_marks=50,
            aptitude_count=25,
            coding_count=25,
            max_attempts=1,
            is_active=True,
        )

        apt_list = [
            QuestionBank(
                prompt=f"Aptitude MCQ {i}",
                section_type=QuestionBank.SectionType.APTITUDE,
                category="Quantitative",
                difficulty="MEDIUM",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_option="A",
                is_active=True,
            )
            for i in range(30)
        ]
        QuestionBank.objects.bulk_create(apt_list)

        cod_list = [
            QuestionBank(
                prompt=f"Coding MCQ {i}",
                section_type=QuestionBank.SectionType.CODING,
                category="Python",
                difficulty="MEDIUM",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_option="B",
                is_active=True,
            )
            for i in range(30)
        ]
        QuestionBank.objects.bulk_create(cod_list)

    def test_burst_load_100_concurrent_students(self):
        num_students = 100
        print(f"\n[LOAD TEST] Starting burst test with {num_students} simultaneous students...")

        start_time = time.time()
        success_regs = 0
        success_starts = 0
        success_submits = 0

        import uuid
        from django.db import connection
        run_id = uuid.uuid4().hex[:6]

        def simulate_student_flow(i):
            client = Client()
            email = f"student_{run_id}_{i:03d}@loadtest.in"
            reg_no = f"LOAD-{run_id}-{i:03d}"

            try:
                # Step 1: Registration
                reg_res = client.post(
                    "/api/assessment/register/",
                    {
                        "full_name": f"Student {i}",
                        "register_number": reg_no,
                        "college": "CSL Engineering Institute",
                        "email": email,
                        "department": "Computer Science",
                        "year_of_study": "Final Year",
                    },
                    content_type="application/json",
                )
                if reg_res.status_code != 201:
                    return False, f"reg_fail: {reg_res.status_code} {reg_res.content[:100]}"

                token = reg_res.data["assessment_token"]
                headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

                # Step 2: Start Assessment
                start_res = client.post("/api/assessment/start/", {}, content_type="application/json", **headers)
                if start_res.status_code != 200:
                    return False, f"start_fail: {start_res.status_code} {start_res.content[:100]}"

                attempt_id = start_res.data["id"]
                attempt_token = start_res.data["assessment_token"]
                attempt_headers = {"HTTP_AUTHORIZATION": f"Bearer {attempt_token}"}

                # Step 3: Answer questions 1 and 2
                ans1 = client.post(
                    f"/api/assessment/attempts/{attempt_id}/answer/",
                    {"question_order": 1, "selected_option": "A"},
                    content_type="application/json",
                    **attempt_headers,
                )
                ans2 = client.post(
                    f"/api/assessment/attempts/{attempt_id}/answer/",
                    {"question_order": 26, "selected_option": "B"},
                    content_type="application/json",
                    **attempt_headers,
                )
                if ans1.status_code != 200 or ans2.status_code != 200:
                    return False, f"ans_fail: {ans1.status_code}/{ans2.status_code}"

                # Step 4: Finalize
                fin_res = client.post(f"/api/assessment/attempts/{attempt_id}/finalize/", **attempt_headers)
                if fin_res.status_code != 200:
                    return False, f"fin_fail: {fin_res.status_code}"

                return True, "success"
            finally:
                connection.close()

        # Concurrently dispatch 100 students using 16 worker threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(simulate_student_flow, i) for i in range(num_students)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        total_duration = time.time() - start_time
        successful = sum(1 for ok, _ in results if ok)
        failures = [msg for ok, msg in results if not ok]
        if failures:
            print(f"[LOAD TEST ERRORS]: Sample error: {failures[0]}")

        print(f"[LOAD TEST] Completed in {total_duration:.2f}s ({successful}/{num_students} passed, {num_students/total_duration:.1f} req/s throughput)")
        self.assertEqual(successful, num_students)
