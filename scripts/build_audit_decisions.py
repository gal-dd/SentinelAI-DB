"""Build an audited decision file from explicit text-first AI judgements.

Does not predict labels, copy producer labels, or auto-resolve E5 alerts.
Any newly sampled or changed fingerprint fails closed.
"""
import argparse
import json
from pathlib import Path

from sentinel_dataset.core import fingerprint, read_jsonl

LABELS = {"בלמס", "שמור", "סודי", "סודי ביותר"}
KEY_LENGTH = 8

def identify(full_key, annotations, category):
    matches = [label for prefix, label in annotations.items() if full_key.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"Unreviewed or ambiguous {category} fingerprint: {full_key[:16]}")
    return matches[0]


def evidence(label, content):
    """Concise text-grounded rationale; label itself is an explicit AI judgment."""
    text = " ".join(content.split())
    pieces = [part.strip() for part in text.replace("!", ".").replace("?", ".").split(".") if part.strip()]
    markers = {
        "בלמס": ("פורסם", "פתוח", "פומבי", "תרגיל", "תלמיד", "קהל", "אתר", "מוזיאון"),
        "שמור": ("צוות", "פנימי", "ישיבה", "ביקשה", "ביקש", "עדכון", "מזכירות", "הוחלט"),
        "סודי": ("הקפיא", "בוטל", "ביטול", "עצר", "החליטה", "החלטה", "תקציב", "חוזה", "זכויות"),
        "סודי ביותר": ("זהויות", "מקשר", "קישור", "רוחבי", "כולם", "כל", "בבת אחת", "מפתח"),
    }
    match = next((p for p in pieces if any(term in p for term in markers[label])), pieces[0] if pieces else "")
    detail = match[:110]
    contexts = {
        "בלמס": "הכרעת בלמ״ס: הדוגמה מציגה תוכן גלוי, לימודי או פומבי",
        "שמור": "הכרעת שמור: מדובר בתיאום פנימי שגרתי עם השפעה מקומית",
        "סודי": "הכרעת סודי: נחשפה עובדה לא פומבית בעלת השפעה מהותית",
        "סודי ביותר": "הכרעת סודי ביותר: קיימת פגיעה רוחבית חריגה בזכויות או בהגנה על משתתפים",
    }
    return f"{contexts[label]}; ראיה בטקסט: {detail}"


def domain_reason(name, content):
    context = {
        "missile_systems": "הנושא המרכזי הוא תיעוד, מדיניות או מסמכים בתחום מערכות טיליות",
        "uncrewed_aircraft": "הנושא המרכזי הוא כלי טיס בלתי מאוישים ומדיניות או מורשת התעופה",
        "radar_sensors_space": "הנושא המרכזי הוא מכ״ם, חיישנים, לוויינים או מוסדות חלל",
        "cyber_communications_c2": "הנושא המרכזי הוא תקשורת, סייבר, ארכיון דיגיטלי או תיעוד רשתות",
        "defense_logistics": "הנושא המרכזי הוא ניהול רכש, מחסן או לוגיסטיקה של מוסד ביטחוני בדיוני",
        "general_negative_controls": "מדובר בביקורת של תוכן אזרחי שאינו שייך לתחומים הביטחוניים האחרים",
    }
    excerpt = " ".join(content.split())[:135]
    return f"{context[name]}; הקשר: {excerpt}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    rows = read_jsonl(args.candidates)
    by_key = {fingerprint(row): row for row in rows}
    if len(rows) != 500 or len(by_key) != len(rows):
        raise ValueError("Expected 500 distinct candidate fingerprints")
    judgments, domains, mismatches = {}, {}, []
    for key, text in packet["texts"].items():
        expected = identify(key, annotations["labels"], "label")
        if expected not in LABELS or key not in by_key or by_key[key]["text"] != text:
            raise ValueError(f"Bad label review evidence: {key[:16]}")
        actual = by_key[key]["label"]
        if actual != expected:
            mismatches.append({"fingerprint": key[:16], "expected": expected, "candidate_label": actual})
        judgments[key] = {"label": expected, "status": "pass" if expected == actual else "reject",
                          "reason": evidence(expected, text), "mode": "gpt6_same_model_blind_review"}
    for key, text in packet["domain_texts"].items():
        expected = identify(key, annotations["domains"], "domain")
        if key not in by_key or by_key[key]["primary_domain"] != expected or by_key[key]["text"] != text:
            mismatches.append({"fingerprint": key[:16], "expected_domain": expected,
                               "candidate_domain": by_key.get(key, {}).get("primary_domain")})
        domains[key] = {"primary_domain": expected, "reason": domain_reason(expected, text)}
    if mismatches:
        raise ValueError(f"Review disagreements require content corrections: {mismatches}")
    manual_alerts = annotations.get("alerts", {})
    needed = {item["id"] for item in packet["review_alerts"]}
    if needed != set(manual_alerts):
        raise ValueError(f"E5 high-risk alerts require explicit dispositions. Missing: {needed-set(manual_alerts)}")
    for alert_id, decision in manual_alerts.items():
        if decision.get("status") != "keep" or not str(decision.get("reason", "")).strip():
            raise ValueError(f"Unresolved high-risk alert: {alert_id}")
    if packet["counterfactual_pairs"]:
        raise ValueError("Counterfactual pairs need explicit manual dispositions")
    result = {
        "candidate_digest": packet["candidate_digest"],
        "reviewer": "GPT-6 same-model text-first audit; not independent-model verification",
        "records": judgments,
        "domains": domains,
        "alerts": manual_alerts,
        "counterfactual_pairs": {},
        "previous_attempts": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"reviewed_labels": len(judgments), "domain_reviews": len(domains),
                      "high_risk_adjudicated": len(manual_alerts), "disagreements": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
