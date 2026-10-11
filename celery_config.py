"""
Celery Configuration for SongShapes Phase 3A: Async Task Processing

Configures Celery to use Redis as message broker and result backend.
Handles task definitions, timeouts, and progress tracking.
"""

from celery import Celery
import os

# Initialize Celery app
celery = Celery('songshapes')

# Redis configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Celery configuration
celery.conf.update(
    # Broker settings (message queue)
    broker_url=REDIS_URL,

    # Result backend (store task results)
    result_backend=REDIS_URL,

    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task execution settings
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit (allows cleanup)

    # Worker settings
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store task_id with result

    # Task routing
    task_routes={
        'celery_tasks.extract_melody_task': {'queue': 'audio_processing'},
        'celery_tasks.detect_chords_task': {'queue': 'audio_processing'},
        'celery_tasks.generate_accompaniment_task': {'queue': 'audio_processing'},
    },
)

# Queue configuration
celery.conf.task_queues = (
    {
        'name': 'audio_processing',
        'exchange': 'audio_processing',
        'routing_key': 'audio_processing',
    },
    {
        'name': 'default',
        'exchange': 'default',
        'routing_key': 'default',
    },
)

# Task base configuration
celery.conf.task_default_queue = 'default'
celery.conf.task_default_exchange_type = 'direct'

# Progress tracking
celery.conf.task_send_sent_event = True  # Enable task_sent event
celery.conf.worker_send_task_events = True  # Send task events

print("✓ Celery configured")
print(f"  Broker: {REDIS_URL}")
print(f"  Result backend: {REDIS_URL}")
print(f"  Result expiration: 1 hour")
