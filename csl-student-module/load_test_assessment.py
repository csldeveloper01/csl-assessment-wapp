#!/usr/bin/env python3
"""
CSL Assessment Platform - Production Load Testing Script
Simulates realistic candidate journeys across staged concurrency tiers (10, 50, 100, 250, 500).

Simulated Journey:
1. Register candidate (POST /api/assessment/register/)
2. Start assessment attempt (POST /api/assessment/start/)
3. Fetch questions snapshot (GET /api/assessment/attempts/<id>/)
4. Submit answers with pacing & batch sync (POST .../answer/ & .../sync-answers/)
5. Heartbeat & keep-alive ping (POST .../heartbeat/)
6. Log integrity proctoring event (POST .../integrity-event/)
7. Finalize and submit assessment (POST .../finalize/)
"""

import sys
import time
import json
import uuid
import random
import argparse
import statistics
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed


class LoadTestRunner:
    def __init__(self, base_url: str, assessment_id: str = None, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.assessment_id = assessment_id
        self.timeout = timeout
        self.results = []
        self.endpoint_timings = defaultdict(list)
        self.endpoint_errors = defaultdict(int)

    def _http_request(self, method: str, path: str, payload: dict = None, token: str = None):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-Assessment-Token"] = token

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                duration_ms = (time.perf_counter() - start) * 1000.0
                body = response.read().decode("utf-8")
                json_data = json.loads(body) if body else {}
                self.endpoint_timings[path].append(duration_ms)
                return True, response.status, json_data, duration_ms
        except urllib.error.HTTPError as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self.endpoint_errors[path] += 1
            return False, e.code, str(e), duration_ms
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self.endpoint_errors[path] += 1
            return False, 0, str(e), duration_ms

    def simulate_candidate(self, candidate_index: int, run_id: str, think_time: float = 0.05):
        client_reg = f"LOAD_{run_id}_{candidate_index:04d}"
        client_email = f"loadtest_{run_id}_{candidate_index:04d}@apex.edu"

        journey_metrics = {
            "candidate_id": client_reg,
            "success": False,
            "total_latency_ms": 0.0,
            "step_latencies": {},
            "error": None,
        }
        journey_start = time.perf_counter()

        # Step 1: Candidate Registration
        reg_payload = {
            "full_name": f"Candidate {candidate_index}",
            "register_number": client_reg,
            "email": client_email,
            "department": "Computer Science",
            "year_of_study": "4",
            "phone_number": f"98765{candidate_index:05d}"[:10],
        }
        ok, status, data, lat = self._http_request("POST", "/api/assessment/register/", reg_payload)
        journey_metrics["step_latencies"]["register"] = lat
        if not ok:
            journey_metrics["error"] = f"Register failed: HTTP {status}"
            journey_metrics["total_latency_ms"] = (time.perf_counter() - journey_start) * 1000
            return journey_metrics

        token = data.get("assessment_token")

        # Step 2: Start Assessment
        start_payload = {"assessment_id": self.assessment_id} if self.assessment_id else {}
        ok, status, data, lat = self._http_request("POST", "/api/assessment/start/", start_payload, token=token)
        journey_metrics["step_latencies"]["start"] = lat
        if not ok:
            journey_metrics["error"] = f"Start failed: HTTP {status}"
            journey_metrics["total_latency_ms"] = (time.perf_counter() - journey_start) * 1000
            return journey_metrics

        attempt_id = data.get("id")
        questions = data.get("questions", [])

        # Step 3: Fetch Attempt State / Questions snapshot
        ok, status, data, lat = self._http_request("GET", f"/api/assessment/attempts/{attempt_id}/", token=token)
        journey_metrics["step_latencies"]["fetch_attempt"] = lat
        if not ok:
            journey_metrics["error"] = f"Fetch state failed: HTTP {status}"
            journey_metrics["total_latency_ms"] = (time.perf_counter() - journey_start) * 1000
            return journey_metrics

        # Step 4: Submit Answers (5 individual answers)
        for q_order in range(1, min(6, len(questions) + 1)):
            if think_time > 0:
                time.sleep(think_time)
            ans_payload = {"question_order": q_order, "selected_option": random.choice(["A", "B", "C", "D"])}
            ok, status, _, lat = self._http_request("POST", f"/api/assessment/attempts/{attempt_id}/answer/", ans_payload, token=token)
            journey_metrics["step_latencies"][f"answer_{q_order}"] = lat

        # Step 5: Send Heartbeat keep-alive
        ok, status, _, lat = self._http_request("POST", f"/api/assessment/attempts/{attempt_id}/heartbeat/", token=token)
        journey_metrics["step_latencies"]["heartbeat"] = lat

        # Step 6: Log Integrity Proctoring Event
        event_payload = {
            "event_type": "TAB_VISIBLE",
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "client_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metadata": {"source": "load_test_suite"},
        }
        ok, status, _, lat = self._http_request("POST", f"/api/assessment/attempts/{attempt_id}/integrity-event/", event_payload, token=token)
        journey_metrics["step_latencies"]["integrity_event"] = lat

        # Step 7: Finalize Assessment
        ok, status, data, lat = self._http_request("POST", f"/api/assessment/attempts/{attempt_id}/finalize/", token=token)
        journey_metrics["step_latencies"]["finalize"] = lat
        if not ok:
            journey_metrics["error"] = f"Finalize failed: HTTP {status}"
            journey_metrics["total_latency_ms"] = (time.perf_counter() - journey_start) * 1000
            return journey_metrics

        journey_metrics["success"] = True
        journey_metrics["total_latency_ms"] = (time.perf_counter() - journey_start) * 1000
        return journey_metrics

    def run_tier(self, concurrency: int, think_time: float = 0.05):
        run_id = uuid.uuid4().hex[:6]
        print(f"\n{'='*75}")
        print(f"▶ RUNNING LOAD TEST TIER: {concurrency} CONCURRENT CANDIDATES")
        print(f"{'='*75}")

        self.endpoint_timings.clear()
        self.endpoint_errors.clear()

        start_time = time.perf_counter()
        results = []

        max_workers = min(concurrency, 64)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.simulate_candidate, i, run_id, think_time)
                for i in range(1, concurrency + 1)
            ]
            for future in as_completed(futures):
                results.append(future.result())

        duration = time.perf_counter() - start_time
        successful = sum(1 for r in results if r["success"])
        failed = concurrency - successful
        total_reqs = sum(len(timings) for timings in self.endpoint_timings.values()) + sum(self.endpoint_errors.values())
        throughput = total_reqs / duration if duration > 0 else 0

        # Overall Journey Latencies
        all_durations = [r["total_latency_ms"] for r in results if r["success"]]
        p50 = statistics.median(all_durations) if all_durations else 0
        p90 = statistics.quantiles(all_durations, n=10)[8] if len(all_durations) >= 10 else p50
        p95 = statistics.quantiles(all_durations, n=20)[18] if len(all_durations) >= 20 else p90
        p99 = statistics.quantiles(all_durations, n=100)[98] if len(all_durations) >= 100 else p95

        print(f"\n--- TIER SUMMARY: {concurrency} CANDIDATES ---")
        print(f"Total Duration:          {duration:.2f}s")
        print(f"Successful Journeys:     {successful}/{concurrency} ({successful/concurrency*100:.1f}%)")
        print(f"Failed Journeys:         {failed}/{concurrency} ({failed/concurrency*100:.1f}%)")
        print(f"Total HTTP Requests:     {total_reqs}")
        print(f"Throughput (RPS):        {throughput:.1f} req/sec")
        print(f"Journey Latency (p50):   {p50:.1f} ms")
        print(f"Journey Latency (p90):   {p90:.1f} ms")
        print(f"Journey Latency (p95):   {p95:.1f} ms")
        print(f"Journey Latency (p99):   {p99:.1f} ms")

        # Per-endpoint breakdown
        print("\n--- PER-ENDPOINT LATENCY BREAKDOWN (ms) ---")
        print(f"{'Endpoint':<45} {'Count':<7} {'p50':<8} {'p95':<8} {'Errors'}")
        print("-" * 75)
        for ep, timings in sorted(self.endpoint_timings.items()):
            ep_p50 = statistics.median(timings) if timings else 0
            ep_p95 = statistics.quantiles(timings, n=20)[18] if len(timings) >= 20 else (statistics.median(timings) if timings else 0)
            errs = self.endpoint_errors.get(ep, 0)
            print(f"{ep:<45} {len(timings):<7} {ep_p50:<8.1f} {ep_p95:<8.1f} {errs}")

        return {
            "concurrency": concurrency,
            "duration_s": duration,
            "successful": successful,
            "failed": failed,
            "throughput_rps": throughput,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
        }


def main():
    parser = argparse.ArgumentParser(description="CSL Assessment Platform Concurrency Load Test")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base backend URL")
    parser.add_argument("--tiers", default="10,50,100,250,500", help="Comma-separated concurrency tiers")
    parser.add_argument("--assessment-id", default=None, help="Target assessment UUID")
    parser.add_argument("--think-time", type=float, default=0.02, help="Pacing between student answers")
    args = parser.parse_args()

    tiers = [int(t.strip()) for t in args.tiers.split(",") if t.strip()]
    runner = LoadTestRunner(base_url=args.url, assessment_id=args.assessment_id)

    print("===========================================================================")
    print("CSL ASSESSMENT PLATFORM: CONCURRENCY STRESS & CAPACITY VALIDATION")
    print(f"Target Server: {args.url}")
    print(f"Evaluation Tiers: {tiers}")
    print("===========================================================================")

    tier_results = []
    for concurrency in tiers:
        res = runner.run_tier(concurrency, think_time=args.think_time)
        tier_results.append(res)
        time.sleep(1)

    print("\n" + "=" * 75)
    print("EXECUTIVE CAPACITY & STRESS EVALUATION SUMMARY")
    print("=" * 75)
    print(f"{'Tier':<10} {'Success':<12} {'RPS':<10} {'p50 (ms)':<12} {'p95 (ms)':<12} {'p99 (ms)'}")
    print("-" * 75)
    for r in tier_results:
        pct = (r["successful"] / r["concurrency"]) * 100
        print(f"{r['concurrency']:<10} {r['successful']}/{r['concurrency']} ({pct:.0f}%) {r['throughput_rps']:<10.1f} {r['p50_ms']:<12.1f} {r['p95_ms']:<12.1f} {r['p99_ms']:.1f}")


if __name__ == "__main__":
    main()
