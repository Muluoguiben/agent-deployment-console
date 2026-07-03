"""CI gate entrypoint:  python -m agent_service.evals [--threshold X] [--model provider:id]

Exit code 0 when the pass rate meets the threshold, 1 otherwise.
"""

import argparse
import json
import sys
from pathlib import Path

from .. import db, registry
from .runner import run_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the triage-agent eval suite")
    parser.add_argument("--model", help="override the live config's model (provider:model-id)")
    parser.add_argument("--threshold", type=float, help="override the gate threshold")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    parser.add_argument("--cases", nargs="*", help="run only these case ids")
    parser.add_argument("--report", type=Path, help="write the JSON report here")
    args = parser.parse_args()

    conn = db.connect()
    db.init_db(conn)
    registry.ensure_seed_version(conn)
    try:
        report = run_suite(
            conn,
            model_override=args.model,
            use_judge=not args.no_judge,
            case_ids=args.cases,
            threshold_override=args.threshold,
        )
    finally:
        conn.close()

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"\nmodel:      {report['model']}")
    print(f"cases:      {report['passed']}/{report['total']} passed "
          f"({report['pass_rate']:.0%}, threshold {report['threshold']:.0%})")
    for result in report["results"]:
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"  [{mark}] {result['case_id']} ({result['category']})")
        if not result["passed"]:
            for check in result["checks"]:
                if not check["passed"]:
                    print(f"         ✗ {check['check']}  {check.get('detail', '')}")
    print(f"\ngate:       {'PASSED' if report['passed_gate'] else 'FAILED'}")
    return 0 if report["passed_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
