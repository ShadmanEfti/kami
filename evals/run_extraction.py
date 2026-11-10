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
    recall_hit = recall_total = 0
    clean_pass = clean_total = 0

    for case in cases:
        candidates = extract_candidates(case["user_messages"], existing=[], blocked=())

        if not case["expected"]:
            ok=not candidates
            clean_total+=1
            clean_pass+=ok
            print(f"\n[{case['id']}] {'✓' if ok else '✗'} expected nothing")
            if candidates:
                print(f"  extracted: {candidates}")
            continue

        hits=[matched(f,candidates) for f in case["expected"]]
        recall_hit+=sum(hits)
        recall_total+=len(hits)

        print(f"\n[{case['id']}] recall {sum(hits)}/{len(hits)}")
        for f,ok in zip(case["expected"],hits):
            print(f"  {'✓' if ok else '✗'} {f['fact']}")
        print(f"  extracted: {candidates}")

    print(f"\nRecall:         {recall_hit}/{recall_total}")
    print(f"No-fact cases:  {clean_pass}/{clean_total} clean")
        

if __name__=="__main__":
    main()