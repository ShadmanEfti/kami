import json
from pathlib import Path
from extractor import extract_candidates

CASES=Path(__file__).parent/"extraction_cases.json"

def matched(fact,candidates):
    return any(
        any(k in c.casefold() for k in fact["any_of"])
        for c in candidates
    )

def main():
    cases=json.loads(CASES.read_text())["cases"]
    total_hit=total=0

    for case in cases:
        candidates=extract_candidates(case["user_messages"],existing=[],blocked=())
        hits=[matched(f,candidates) for f in case["expected"]]

        print(f"\n[{case['id']}] recall {sum(hits)}/{len(hits)}")
        for f,ok in zip(case["expected"],hits):
            print(f"  {'✓' if ok else '✗'} {f['fact']}")
        print(f"  extracted: {candidates}")

        total_hit+=sum(hits)
        total+=len(hits)

    print(f"\nOverall recall:{total_hit}/{total}")


if __name__=="__main__":
    main()