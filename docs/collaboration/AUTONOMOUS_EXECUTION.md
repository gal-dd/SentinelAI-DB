# Autonomous execution — safe assigned deliverables

The goal is a finished, tested, remotely verified deliverable, not a plan or a partially completed draft. Applies to any AI provider, with no prior conversation context.

## Required execution sequence
1. Read START_HERE.md, ASSIGNMENT.md and DATA_BOUNDARY.md. Establish the actual base SHA and assigned task, permitted inputs, output path, permitted publication target and acceptance criteria. Use metadata only for production status.
2. Check tools and access. Never assume an AI chat can run code, authenticate to GitHub, or continue after its turn. If write access is unavailable, use the file-delivery fallback. Do not solicit credentials or bypass restrictions.
3. Implement the whole explicitly assigned safe task. Routine implementation choices are delegated. Do not stop after a plan, first sample, draft, or successful partial check.
4. Check the deliverable against the assignment. Run relevant tests when possible. Read failures, correct the actual issue, and rerun affected checks. Reuse valid evidence only for unchanged inputs. Never fabricate evidence, change expected results merely to pass a test, or skip required checks.
5. Where the owner has already authorized publishing the safe deliverable to its isolated assigned branch or output destination, commit and push the actual output, then verify the remote SHA and contents. Do not ask for routine approval again. Never push a shared production branch or modify another worker's files. If a required check is still running, do not declare success; inspect its result while tools and execution time permit. Do not promise continuous monitoring or unattended retries without a real mechanism.
6. Finish with the submission contract including actual artifacts, remote commit if available, test results, limitations and blockers. If publication of the assigned deliverable is impossible, state exactly why and return the usable output. A published submission is not a production checkpoint.
7. The authorized central coordinator handles acceptance and integration separately, after review, against the current base. Only explicitly cleared safe outputs may be integrated. No external AI has blanket access to unreviewed imports or permission to publish production data. No concurrent production writers.

## When to stop
Stop only on verified completion, a genuine blocker that cannot be resolved within the assignment, a permissions/safety boundary, or an execution limit. Preserve the actual work and report the precise next unresolved condition. Do not repeatedly retry an unchanged deterministic failure. Never weaken quality or safety gates to increase throughput.

Each subsequent task requires its own assigned ID and approved scope. Repeat the same complete sequence; do not infer permission for a new task from a previous one.
