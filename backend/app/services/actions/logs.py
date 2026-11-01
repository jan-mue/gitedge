"""Archive before ACK; Redis accelerates delivery but never owns history."""

from __future__ import annotations

from app.exceptions import ConflictError, NotFoundError, PermissionDeniedError

import asyncio
import hashlib
import logging
import time
import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.actions import WorkflowLogChunk
from app.exceptions import ActionsUnavailableError
from app.schemas.action_logs import LOG_PAGE_BYTES, LOG_STREAM_SECONDS, LogChunk, LogPage, LogRecord
from app.services.actions.capabilities import authorize_report, report_payload
from app.services.actions.runtime import redact
from app.services.actions.scheduler import TERMINAL

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.clients.action_logs import ActionsLogStore
    from app.clients.actions import ActionsStore, RunState
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.redis import AbstractRedisClient
    from app.entities.actions import WorkflowAttempt
    from app.schemas.action_dispatch import Capability

logger = logging.getLogger(__name__)
MAX_PAGE_RECORDS = 1000


def current_attempt(state: RunState | None, capability: Capability, *, terminal: bool = False) -> WorkflowAttempt:
    """Recheck fencing under the run lock before applying a report."""
    attempt = state.attempt(capability.id) if state else None
    job = state.job(attempt) if state and attempt else None
    if (
        not state
        or not attempt
        or not job
        or state.run.status == "cancelled"
        or attempt.fence != capability.fence
        or attempt.generation != capability.generation
        or attempt.job_id != capability.job_id
        or (job.status in TERMINAL and not terminal)
    ):
        raise PermissionDeniedError("Sandbox capability is stale")
    return attempt


class ActionsLogService:
    """Archive immutable chunks and serve resumable bounded output."""

    def __init__(
        self,
        runs: ActionsStore,
        indexes: ActionsLogStore,
        blobs: BlobStorageClient,
        redis: AbstractRedisClient,
        secrets: dict[str, dict[str, str]],
    ) -> None:
        """Combine authoritative indexes and objects with an optional Redis tail."""
        self.runs, self.indexes, self.blobs, self.redis, self.secrets = runs, indexes, blobs, redis, secrets

    async def upload(self, attempt_id: uuid.UUID, authorization: str, body: bytes) -> int:
        """Archive and atomically index a chunk before acknowledging its sequence."""
        capability = await authorize_report(self.runs, attempt_id, authorization, terminal=True)
        chunk = report_payload(LogChunk, body, capability)
        for record in chunk.records:
            record.msg = redact(record.msg, self.secrets.get(str(capability.repo), {}))
        payload = chunk.model_dump_json().encode()
        checksum = hashlib.sha256(payload).hexdigest()
        chunk_id = uuid.uuid5(attempt_id, str(chunk.from_seq))
        key = f"actions/{capability.repo}/{capability.run}/attempts/{attempt_id}/logs/{chunk.from_seq}-{checksum}.json"
        await self.blobs.put(key, payload)
        async with self.runs.transaction(capability.run, capability.repo) as state:
            attempt = current_attempt(state, capability, terminal=True)
            if chunk.from_seq <= (attempt.log_seq or 0):
                previous = await self.indexes.chunk(chunk_id)
                if not previous or previous.checksum != checksum or previous.to_seq != chunk.to_seq:
                    raise ConflictError("Log retry changed a committed chunk")
            elif attempt.status not in {"starting", "running"}:
                raise PermissionDeniedError("Attempt has completed")
            elif chunk.from_seq != (attempt.log_seq or 0) + 1:
                raise ConflictError("Log sequence has a gap")
            else:
                self.indexes.stage(
                    WorkflowLogChunk(
                        id=chunk_id,
                        attempt_id=attempt_id,
                        from_seq=chunk.from_seq,
                        to_seq=chunk.to_seq,
                        checksum=checksum,
                        object_key=key,
                        size=len(payload),
                    )
                )
                attempt.log_seq = chunk.to_seq
        try:
            async with asyncio.timeout(0.25):
                await self.redis.stream_add(self._tail(attempt_id), chunk.to_seq, payload.decode())
        except Exception:
            logger.warning("Recent Actions log delivery unavailable", exc_info=True)
        return chunk.to_seq

    async def page(self, repo_id: uuid.UUID, run_id: uuid.UUID, attempt_id: uuid.UUID, after: int) -> LogPage:
        """Read contiguous records from the recent tail or immutable archive."""
        context = await self.indexes.context(repo_id, run_id, attempt_id)
        if not context:
            raise NotFoundError("Workflow attempt not found")
        records: list[LogRecord] = []
        try:
            async with asyncio.timeout(0.25):
                entries = await self.redis.stream_read(self._tail(attempt_id), after)
            cached = [
                record for raw in entries for record in LogChunk.model_validate_json(raw).records if record.seq > after
            ]
            for record in cached:
                if record.seq != after + len(records) + 1 or record.seq > context.log_seq:
                    break
                records.append(record)
        except Exception:
            logger.warning("Replaying archived Actions logs", exc_info=True)
        if not records and after < context.log_seq:
            for index in await self.indexes.chunks(attempt_id, after):
                payload = await self.blobs.get_current(index.object_key)
                if payload is None or hashlib.sha256(payload).hexdigest() != index.checksum:
                    raise ActionsUnavailableError("Archived log chunk is missing or corrupt")
                chunk = LogChunk.model_validate_json(payload)
                records.extend(record for record in chunk.records if after < record.seq <= context.log_seq)
        bounded: list[LogRecord] = []
        size = 0
        for record in records:
            size += len(record.model_dump_json().encode())
            if size > LOG_PAGE_BYTES or len(bounded) >= MAX_PAGE_RECORDS:
                break
            if record.seq != after + len(bounded) + 1:
                raise ActionsUnavailableError("Archived log sequence is incomplete")
            bounded.append(record)
        cursor = bounded[-1].seq if bounded else after
        return LogPage(
            attempt_id=attempt_id,
            records=bounded,
            next_seq=cursor,
            complete=context.status not in {"queued", "starting", "running"} and cursor >= context.log_seq,
        )

    async def stream(
        self,
        repo_id: uuid.UUID,
        run_id: uuid.UUID,
        attempt_id: uuid.UUID,
        after: int,
    ) -> AsyncIterator[str]:
        """Yield resumable SSE records within a bounded connection lifetime."""
        deadline = time.monotonic() + LOG_STREAM_SECONDS
        delay = 0.1
        while time.monotonic() < deadline:
            page = await self.page(repo_id, run_id, attempt_id, after)
            for record in page.records:
                yield f"id: {record.seq}\nevent: log\ndata: {record.model_dump_json()}\n\n"
            after = page.next_seq
            if page.complete:
                yield f'event: end\ndata: {{"last_seq":{after}}}\n\n'
                return
            if page.records:
                delay = 0.1
            else:
                yield ": keepalive\n\n"
                await asyncio.sleep(delay)
                delay = min(1, delay * 2)

    @staticmethod
    def _tail(attempt_id: uuid.UUID) -> str:
        return f"actions:logs:{attempt_id}"

    async def download(self, repo_id: uuid.UUID, run_id: uuid.UUID, attempt_id: uuid.UUID) -> AsyncIterator[str]:
        """Stream text through the cursor committed when the download started."""
        context = await self.indexes.context(repo_id, run_id, attempt_id)
        if context is None:
            raise NotFoundError("Workflow attempt not found")
        after = 0
        while after < context.log_seq:
            page = await self.page(repo_id, run_id, attempt_id, after)
            if not page.records:
                raise ActionsUnavailableError("Log archive is incomplete")
            for record in page.records:
                if record.seq > context.log_seq:
                    return
                yield record.msg + ("\n" if record.end else "")
            after = page.next_seq
