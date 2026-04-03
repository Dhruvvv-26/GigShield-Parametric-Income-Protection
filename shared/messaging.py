"""
GigShield — Shared Redpanda / Kafka Messaging
Producer: used by Trigger Engine to emit events.
Consumer base: used by Claims Service (Week 4).

All topics are defined centrally in shared/config.py.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Message Schema ────────────────────────────────────────────────────────────

def build_message(
    event_type: str,
    payload: dict[str, Any],
    source_service: str,
) -> dict[str, Any]:
    """
    Standard GigShield message envelope.
    Every message published to Redpanda uses this schema.
    """
    return {
        "message_id": str(uuid.uuid4()),
        "event_type": event_type,
        "source_service": source_service,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "payload": payload,
    }


# ── Producer ──────────────────────────────────────────────────────────────────

class GigShieldProducer:
    """
    Async Kafka producer backed by Redpanda.
    Instantiate once at service startup, call close() at shutdown.
    """

    def __init__(self):
        self._producer: AIOKafkaProducer | None = None
        self._brokers = settings.redpanda_brokers

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._brokers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",           # Wait for all replicas
            compression_type="gzip",
            max_batch_size=16384,
            linger_ms=5,          # Small batching window
            retry_backoff_ms=100,
            request_timeout_ms=30000,
        )
        await self._producer.start()
        logger.info(f"Redpanda producer connected to {self._brokers} ✓")

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Redpanda producer stopped ✓")

    async def publish(
        self,
        topic: str,
        event_type: str,
        payload: dict[str, Any],
        source_service: str,
        key: str | None = None,
    ) -> None:
        """
        Publish a message to a Redpanda topic.
        key is used for partition routing (e.g., zone_id for ordering).
        """
        if self._producer is None:
            raise RuntimeError("Producer not started. Call start() first.")

        message = build_message(event_type, payload, source_service)

        try:
            await self._producer.send_and_wait(
                topic=topic,
                value=message,
                key=key,
            )
            logger.debug(
                f"Published {event_type} to {topic}",
                extra={"message_id": message["message_id"]},
            )
        except KafkaConnectionError as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            raise


# ── Consumer Base ─────────────────────────────────────────────────────────────

class GigShieldConsumer:
    """
    Async Kafka consumer base class.
    Subclass and implement process_message() for each consumer.
    """

    def __init__(self, topics: list[str], group_id: str):
        self._topics = topics
        self._group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=settings.redpanda_brokers,
            group_id=self._group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,   # Manual commit for at-least-once
            max_poll_records=100,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            f"Consumer {self._group_id} subscribed to {self._topics} ✓"
        )

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info(f"Consumer {self._group_id} stopped ✓")

    async def consume(self) -> None:
        """Main consume loop. Override process_message() to handle messages."""
        if self._consumer is None:
            raise RuntimeError("Consumer not started. Call start() first.")

        async for msg in self._consumer:
            if not self._running:
                break
            try:
                await self.process_message(msg.value)
                await self._consumer.commit()
            except Exception as e:
                logger.error(
                    f"Error processing message in {self._group_id}: {e}",
                    exc_info=True,
                )
                # Don't commit — message will be reprocessed
                # Add dead-letter logic in Phase 3

    async def process_message(self, message: dict[str, Any]) -> None:
        """Override in subclasses to implement message processing logic."""
        raise NotImplementedError
