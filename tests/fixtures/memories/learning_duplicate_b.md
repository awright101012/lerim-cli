---
name: Webhook retries cause duplicates without idempotency keys
description: Webhook retry mechanism sends duplicate payloads without idempotency keys
type: feedback
id: learning-webhook-dedup-b
created: 2026-02-19T11:00:00Z
updated: 2026-02-19T11:00:00Z
source: sync-20260219-110000-dup002
---

Discovered that webhook retry mechanism was sending duplicate payloads. Solution: add idempotency keys (UUIDs) to every webhook call so receivers can deduplicate.
