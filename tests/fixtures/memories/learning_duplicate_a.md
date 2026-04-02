---
name: Add idempotency keys to prevent duplicate webhook deliveries
description: Retry logic caused duplicate webhook deliveries; fixed with UUID idempotency keys
type: feedback
id: learning-retry-idempotency-a
created: 2026-02-18T16:00:00Z
updated: 2026-02-18T16:00:00Z
source: sync-20260218-160000-dup001
---

Retry logic caused duplicate webhook deliveries. Fixed by adding UUID-based idempotency keys to all webhook payloads.
