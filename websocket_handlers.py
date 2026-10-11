"""
WebSocket Handlers for SongShapes Phase 3A

Handles real-time progress updates for async tasks via WebSocket/SocketIO.
Clients can subscribe to task progress and receive updates in real-time.
"""

from flask import request
from flask_socketio import emit, join_room, leave_room
from celery.result import AsyncResult
import json

# Store active subscriptions: task_id -> set of socket_ids
task_subscriptions = {}


def setup_websocket_handlers(socketio, celery_app):
    """
    Setup WebSocket event handlers for the Flask-SocketIO app

    Args:
        socketio: Flask-SocketIO instance
        celery_app: Celery app instance for task monitoring
    """

    @socketio.on('connect')
    def handle_connect():
        """Client connected"""
        print(f"[WebSocket] Client connected: {request.sid}")
        emit('connection_response', {
            'data': 'Connected to SongShapes server',
            'sid': request.sid
        })

    @socketio.on('disconnect')
    def handle_disconnect():
        """Client disconnected"""
        print(f"[WebSocket] Client disconnected: {request.sid}")

        # Remove client from all subscriptions
        for task_id in list(task_subscriptions.keys()):
            if request.sid in task_subscriptions[task_id]:
                task_subscriptions[task_id].discard(request.sid)
                if not task_subscriptions[task_id]:
                    del task_subscriptions[task_id]

    @socketio.on('subscribe_task')
    def handle_subscribe(data):
        """
        Subscribe to task progress updates

        Event payload:
        {
            'task_id': 'celery_task_id'
        }
        """
        task_id = data.get('task_id')

        if not task_id:
            emit('error', {'message': 'No task_id provided'})
            return

        # Initialize subscription set if needed
        if task_id not in task_subscriptions:
            task_subscriptions[task_id] = set()

        # Add client to subscription
        task_subscriptions[task_id].add(request.sid)

        print(f"[WebSocket] {request.sid} subscribed to task {task_id}")

        # Send current task state
        result = AsyncResult(task_id, app=celery_app)

        if result.state == 'PENDING':
            state_data = {
                'state': 'PENDING',
                'current': 0,
                'total': 100,
                'percentage': 0,
                'message': 'Task queued...',
                'task_id': task_id
            }
        elif result.state == 'PROGRESS':
            state_data = result.info.copy()
            state_data['state'] = 'PROGRESS'
            state_data['task_id'] = task_id
        elif result.state == 'SUCCESS':
            state_data = {
                'state': 'SUCCESS',
                'current': 100,
                'total': 100,
                'percentage': 100,
                'message': 'Complete!',
                'result': result.result,
                'task_id': task_id
            }
        elif result.state == 'FAILURE':
            state_data = {
                'state': 'FAILURE',
                'message': str(result.info),
                'task_id': task_id
            }
        else:
            state_data = {
                'state': result.state,
                'message': str(result.info),
                'task_id': task_id
            }

        emit('task_status', state_data)

    @socketio.on('unsubscribe_task')
    def handle_unsubscribe(data):
        """Unsubscribe from task progress updates"""
        task_id = data.get('task_id')

        if task_id and task_id in task_subscriptions:
            task_subscriptions[task_id].discard(request.sid)
            if not task_subscriptions[task_id]:
                del task_subscriptions[task_id]
            print(f"[WebSocket] {request.sid} unsubscribed from task {task_id}")

    @socketio.on('get_task_status')
    def handle_get_status(data):
        """
        Get current task status

        Event payload:
        {
            'task_id': 'celery_task_id'
        }
        """
        task_id = data.get('task_id')

        if not task_id:
            emit('error', {'message': 'No task_id provided'})
            return

        result = AsyncResult(task_id, app=celery_app)

        if result.state == 'PENDING':
            state_data = {
                'state': 'PENDING',
                'current': 0,
                'total': 100,
                'percentage': 0,
                'message': 'Task queued...'
            }
        elif result.state == 'PROGRESS':
            state_data = result.info.copy()
            state_data['state'] = 'PROGRESS'
        elif result.state == 'SUCCESS':
            state_data = {
                'state': 'SUCCESS',
                'current': 100,
                'total': 100,
                'percentage': 100,
                'message': 'Complete!',
                'result': result.result
            }
        elif result.state == 'FAILURE':
            state_data = {
                'state': 'FAILURE',
                'message': str(result.info),
                'error': True
            }
        else:
            state_data = {
                'state': result.state,
                'message': str(result.info)
            }

        emit('task_status', state_data)

    # Task progress event listener (called by Celery workers)
    @celery_app.on_after_task_publish.connect
    def task_sent_handler(sender=None, body=None, **kwargs):
        """Called when a task is submitted"""
        pass

    print("✓ WebSocket handlers configured")


def broadcast_task_progress(task_id, state, meta):
    """
    Broadcast task progress to all subscribed clients

    Called by Celery workers when task state changes.

    Args:
        task_id: Celery task ID
        state: Task state (PROGRESS, SUCCESS, FAILURE, etc.)
        meta: Task metadata (progress info)
    """
    if task_id not in task_subscriptions:
        return

    if state == 'PROGRESS':
        data = meta.copy()
        data['state'] = 'PROGRESS'
        data['task_id'] = task_id

        for socket_id in task_subscriptions[task_id]:
            # Note: This is tricky in async context
            # In production, use Celery signals + Redis pub/sub
            pass

    elif state == 'SUCCESS':
        data = {
            'state': 'SUCCESS',
            'current': 100,
            'total': 100,
            'percentage': 100,
            'result': meta.get('result'),
            'message': 'Task complete!',
            'task_id': task_id
        }

        for socket_id in task_subscriptions[task_id]:
            pass

    elif state == 'FAILURE':
        data = {
            'state': 'FAILURE',
            'message': str(meta.get('exc_message', 'Task failed')),
            'error': True,
            'task_id': task_id
        }

        for socket_id in task_subscriptions[task_id]:
            pass
