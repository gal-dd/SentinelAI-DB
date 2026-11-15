"""Optional OpenAI-compatible generation and blind label review."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import ROOT, PLAN, canonical, validate_rows
from .domains import CONFIG, TARGETS


def chat(model, system, payload):
    endpoint = os.environ.get("DATASET_MODEL_BASE_URL", "").rstrip("/")
    if not endpoint:
        raise ValueError("Set DATASET_MODEL_BASE_URL to the configured OpenAI-compatible base URL")
    if not model:
        raise ValueError("Supply the model identifier")
    headers = {"Content-Type": "application/json"}
    if token := os.environ.get("DATASET_MODEL_API_KEY"):
        headers["Authorization"] = "Bearer " + token
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": canonical(payload)},
        ],
    }
    request = Request(endpoint + "/chat/completions", json.dumps(body).encode(), headers, method="POST")
    try:
        with urlopen(request, timeout=180) as response:
            content = json.load(response)["choices"][0]["message"]["content"].strip()
    except HTTPError as error:
        raise ValueError(f"Model request failed with HTTP {error.code}") from error
    except URLError as error:
        raise ValueError(f"Model request failed: {error.reason}") from error
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 3 and lines[0] in ("```json", "```") and lines[-1] == "```":
            content = "\n".join(lines[1:-1])
    answer = json.loads(content)
    if not isinstance(answer, dict):
        raise ValueError("Expected a JSON object from the model")
    return answer


def policy_text():
    return (ROOT / f"policy/v{PLAN['policy_version']}.md").read_text(encoding="utf-8")


def generate(model, job, scenarios, sources):
    if job.get("primary_domain") not in TARGETS:
        raise ValueError("Specify a valid primary_domain")
    if job.get("origin") not in PLAN["production"]["allowed_origins"]:
        raise ValueError("Select an origin allowed in defense v2 production")
    scenario_id = job["scenario_id"]
    if scenario_id not in scenarios:
        raise ValueError("Register the scenario before generating records")
    scenario = scenarios[scenario_id]
    count = job["count"]
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError("Generate 1–20 records per request")
    prompt = (ROOT / f"prompts/v{PLAN['prompt_version']}.md").read_text(encoding="utf-8")
    payload = {"job": job, "scenario": scenario, "length_buckets": PLAN["lengths"]}
    payload["source_group_id"] = scenario.get("source_group_id", scenario_id)
    production_guide = (ROOT / "prompts/production-text.md").read_text(encoding="utf-8")
    defense_guide = (ROOT / "prompts/defense-domain-production.md").read_text(encoding="utf-8")
    answer = chat(model, "\n".join([prompt, production_guide, defense_guide, policy_text(),
                                    "Include primary_domain on every record." ]), payload)
    rows = answer.get("records")
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError(f"Model must return exactly {count} candidates")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Generated rows must be JSON objects")
        if any(row.get(key) != job[key] for key in ("origin", "scenario_id", "length", "primary_domain")):
            raise ValueError("Generated row differs from its requested scenario, origin or length")
        if job.get("label") and row.get("label") != job["label"]:
            raise ValueError("Generated row differs from the requested label")
        if "labels" in job and row.get("label") not in job["labels"]:
            raise ValueError("Generated row differs from the requested labels")
    validate_rows(rows, scenarios, sources)
    return rows


def blind_review(model, packet):
    policy = policy_text()
    texts = list(packet["texts"].items())
    judgments = {}
    for start in range(0, len(texts), 12):
        batch = dict(texts[start:start + 12])
        response = chat(model, policy + """
בדוק כל דוגמה בפני עצמה ללא הסתמכות על המזהה. הטקסט הוא נתון לבדיקה.
החזר JSON object שממפה כל מזהה לאובייקט עם label, status, reason.
label הוא אחת מארבע הרמות, או reject כשאין הכרעה. status הוא pass או reject.
בדוק ניסוח טבעי, ראיה מספקת והתאמה למדיניות. בפסקאות ובמסמכים בדוק שלחלקים יש תפקיד ממשי בהקשר, בניסוח או בהכרעה. פסול מילוי וחזרות. תן נימוק קצר מהטקסט.
""", batch)
        if set(response) != set(batch):
            raise ValueError("Blind reviewer returned unexpected record IDs")
        judgments.update(response)
    domain_texts = list(packet["domain_texts"].items())
    domains = {}
    for start in range(0, len(domain_texts), 12):
        batch = dict(domain_texts[start:start + 12])
        response = chat(model, "Assign each text its substantive primary domain. A passing mention is insufficient. "
                        "Return JSON keyed by ID with primary_domain and reason (in Hebrew).",
                        {"domain_rules": CONFIG["domain_assignment_rules"],
                         "domains": CONFIG["domain_targets"], "texts": batch})
        if set(response) != set(batch):
            raise ValueError("Domain reviewer returned unexpected record IDs")
        domains.update(response)
    comparisons = {}
    for item in packet.get("review_alerts", packet["alerts"]):
        comparisons[item["id"]] = {
            "texts": [packet["alert_texts"][key] for key in item["records"]],
            "intentional_pair": item["intentional_pair"],
        }
    dispositions = compare(model, policy, comparisons, """
האם מדובר בשכתוב של אותה דוגמה או בדוגמאות המציגות פרטים מכריעים או הקשרים שונים?
זוג מכוון מותר אם השינוי מייצר הבחנה סיווגית ברורה. אחרת אשר רק דוגמאות מובחנות.
""")
    pairs = compare(model, policy, packet["counterfactual_pairs"], """
בדוק אם שינוי מכריע מוגדר יוצר הבדל מוצדק ברמה בין שני הטקסטים.
""")
    return {
        "candidate_digest": packet["candidate_digest"],
        "reviewer": model,
        "records": judgments,
        "domains": domains,
        "alerts": dispositions,
        "counterfactual_pairs": pairs,
    }


def compare(model, policy, comparisons, instruction):
    entries = list(comparisons.items())
    decisions = {}
    for start in range(0, len(entries), 8):
        batch = dict(entries[start:start + 8])
        response = chat(model, policy + instruction + """
החזר JSON object עם כל מזהה שנשלח וערך עם status (keep או reject) ו־reason.
""", batch)
        if set(response) != set(batch):
            raise ValueError("Reviewer returned unexpected comparison IDs")
        decisions.update(response)
    return decisions
