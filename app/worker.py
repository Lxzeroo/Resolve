"""Durable Slack outbox worker with retry/backoff. Run: python -m app.worker"""
import asyncio
import os
import random
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.main import AuditEvent, Base, Job, SessionLocal, Ticket, engine
from app.integrations import slack_send


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def process_once() -> int:
    """Single worker only: no multi-worker leasing or advisory locks yet."""
    with SessionLocal() as db:
        jobs = db.scalars(select(Job).where(Job.status == 'pending', Job.next_attempt_at <= utcnow())
                          .order_by(Job.id).limit(10)).all()
        ids = [j.id for j in jobs]
    processed = 0
    for jid in ids:
        with SessionLocal() as db:
            job = db.get(Job, jid)
            if not job or job.status != 'pending':
                continue
            ticket = db.get(Ticket, job.ticket_id)
            if not ticket:
                job.status = 'failed'
                db.commit()
                continue
            try:
                retry_after = await slack_send(ticket.id, ticket.priority, ticket.category, ticket.subject)
                if retry_after is not None:
                    raise RetryNeeded(retry_after)
                job.status = 'done'
                db.add(AuditEvent(ticket_id=ticket.id, event='slack_escalated', details='Slack webhook accepted'))
            except Exception as exc:
                job.attempts += 1
                job.status = 'failed' if job.attempts >= 5 else 'pending'
                delay = exc.delay if isinstance(exc, RetryNeeded) else min(3600, 2 ** job.attempts * 15)
                job.next_attempt_at = utcnow() + timedelta(seconds=delay)
                # Never store exception strings, which may leak webhook credentials.
                job.last_error = type(exc).__name__[:80]
                db.add(AuditEvent(ticket_id=ticket.id, event='slack_delivery_retry' if job.status == 'pending' else 'slack_delivery_failed', details=f'Attempt {job.attempts}'))
            db.commit()
            processed += 1
    return processed


class RetryNeeded(Exception):
    def __init__(self, delay: float):
        self.delay = delay


async def main():
    Base.metadata.create_all(engine)
    once = '--once' in __import__('sys').argv
    while True:
        await process_once()
        if once:
            break
        await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(main())
