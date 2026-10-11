# SongShapes Phase 3A: Async Task Processing with Celery/Redis

**Date**: October 11, 2026  
**Status**: Planning → Implementation  
**Goal**: Enable long-running operations without blocking the UI

---

## Architecture Overview

### Current (Synchronous)
```
POST /api/extract-melody
  → Block for 0.5s
  → Return F0 contour
  → User waits
```

### Target (Asynchronous)
```
POST /api/extract-melody
  → Queue task immediately
  → Return task_id + status URL
  → User polls for progress
  ↓
GET /api/task-status/<task_id>
  → Return { status: "processing", progress: 45% }
  ↓
WebSocket /ws/task-progress/<task_id>
  → Stream progress updates in real-time
  ↓
GET /api/task-result/<task_id>
  → Return F0 contour once complete
```

---

## Implementation Plan

### Phase 3A.1: Setup (Day 1)
- [ ] Install Celery + Redis dependencies
- [ ] Configure Celery app and broker (Redis)
- [ ] Create celery_tasks.py with task definitions
- [ ] Update app.py to queue tasks instead of blocking
- [ ] Add task status tracking endpoints

### Phase 3A.2: WebSocket Integration (Day 1.5)
- [ ] Install flask-socketio + python-socketio
- [ ] Create WebSocket handler for task progress
- [ ] Update task workers to emit progress updates
- [ ] Test real-time progress streaming

### Phase 3A.3: Frontend Integration (Day 2)
- [ ] Update UI to show task_id + progress bar
- [ ] Connect WebSocket listener in JavaScript
- [ ] Display real-time progress percentage
- [ ] Handle task completion and result retrieval

### Phase 3A.4: Testing (Day 2.5)
- [ ] Verify Celery workers start correctly
- [ ] Test all three async tasks
- [ ] Verify WebSocket progress updates
- [ ] Test concurrent tasks (multiple users)

---

## Files to Create/Modify

### New Files
- `celery_config.py` — Celery configuration (Redis broker, task defaults)
- `celery_tasks.py` — Task definitions (extract_melody, detect_chords, generate_accompaniment)
- `websocket_handlers.py` — WebSocket event handlers for progress updates

### Modified Files
- `app.py` — Add async endpoints, task status routes, WebSocket initialization
- `templates/songshapes.html` — Add progress bar, WebSocket listener, async polling

### Dependencies (requirements.txt)
```
celery>=5.3.0
redis>=5.0.0
flask-socketio>=5.3.0
python-socketio>=5.9.0
python-engineio>=4.7.0
```

---

## Task Definitions

### Task 1: extract_melody_task
```python
@celery.task(bind=True)
def extract_melody_task(self, session_id):
    """
    Extract F0 contour from vocals stem
    
    Progress updates:
    - 20%: Audio loaded
    - 40%: STFT computed
    - 60%: Autocorrelation calculated
    - 80%: Confidence scoring
    - 100%: Complete
    """
    self.update_state(state='PROGRESS', meta={'current': 20})
    # Load vocals stem...
    
    self.update_state(state='PROGRESS', meta={'current': 40})
    # Compute STFT...
    
    # ... continue with progress updates
    
    return {
        'f0_mean': 440.5,
        'voicing_ratio': 0.82,
        'num_frames': 344
    }
```

### Task 2: detect_chords_task
```python
@celery.task(bind=True)
def detect_chords_task(self, session_id):
    """
    Detect chord progression
    
    Progress: 0% → 50% (chromagram) → 100% (template matching)
    """
    return {
        'chords': [...],
        'num_chords': 2
    }
```

### Task 3: generate_accompaniment_task
```python
@celery.task(bind=True)
def generate_accompaniment_task(self, session_id, tempo_bpm, key, character_config):
    """
    Generate bass + drums accompaniment
    
    Progress: 0% → 33% (bass) → 66% (drums) → 100% (mix)
    """
    return {
        'accompaniment_stems': {...},
        'metadata': {...}
    }
```

---

## API Endpoints

### Async Task Submission
```bash
POST /api/extract-melody-async
{
  "session_id": "abc123"
}
→ { "status": "queued", "task_id": "task_xyz", "status_url": "/api/task-status/task_xyz" }
```

### Task Status Polling
```bash
GET /api/task-status/<task_id>
→ { "state": "PROGRESS", "current": 45, "total": 100, "message": "Computing STFT..." }
```

### Task Result Retrieval
```bash
GET /api/task-result/<task_id>
→ { "status": "success", "result": {...} }
```

### WebSocket Progress Stream
```javascript
const socket = io();
socket.on('connect', () => {
  socket.emit('subscribe_task', { task_id: 'task_xyz' });
});
socket.on('task_progress', (data) => {
  console.log(`Progress: ${data.current}%`);
  updateProgressBar(data.current);
});
socket.on('task_complete', (data) => {
  console.log('Task finished:', data.result);
});
```

---

## Frontend Changes

### HTML Progress Display
```html
<div id="phase2-async">
  <div id="task-status" style="display:none;">
    <p id="task-message">Processing...</p>
    <progress id="task-progress" value="0" max="100"></progress>
    <span id="task-percentage">0%</span>
  </div>
</div>
```

### JavaScript WebSocket Handler
```javascript
const socket = io();

async function extractMelodyAsync() {
  const response = await fetch('/api/extract-melody-async', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSessionId })
  });
  
  const data = await response.json();
  const taskId = data.task_id;
  
  // Subscribe to progress updates
  socket.emit('subscribe_task', { task_id: taskId });
  
  // Listen for progress
  socket.on('task_progress', (update) => {
    if (update.task_id === taskId) {
      document.getElementById('task-progress').value = update.current;
      document.getElementById('task-percentage').textContent = `${update.current}%`;
    }
  });
  
  // Listen for completion
  socket.on('task_complete', (result) => {
    if (result.task_id === taskId) {
      displayF0Waveform(result.f0_contour);
      phase2State.f0_extracted = true;
    }
  });
}
```

---

## Celery Worker Configuration

### Start Worker
```bash
celery -A celery_tasks worker --loglevel=info
```

### Monitor Tasks
```bash
celery -A celery_tasks events
# or use Flower (web UI)
pip install flower
celery -A celery_tasks flower
```

---

## Testing Strategy

### Unit Tests
- [ ] Task functions return correct structure
- [ ] Progress updates emit correctly
- [ ] Error handling (missing audio, invalid session)

### Integration Tests
- [ ] Submit task → receive task_id
- [ ] Poll status endpoint → get progress
- [ ] WebSocket connection → receive updates
- [ ] Result retrieval → get output

### Load Tests
- [ ] Submit 10 concurrent tasks
- [ ] Verify all complete without interference
- [ ] Check memory usage with Celery workers

---

## Deployment Checklist

- [ ] Redis server running (locally or hosted)
- [ ] Celery workers started (1+ processes)
- [ ] Flask app with SocketIO initialized
- [ ] WebSocket gateway configured
- [ ] Frontend JavaScript listening for updates
- [ ] Progress bar UI rendering correctly

---

## Known Limitations

1. **Task Results Expire** — Results cleared after 1 hour (configurable)
2. **No Task Persistence** — Tasks lost on Redis restart (Phase 1: Database stores task history)
3. **Single Redis Instance** — No redundancy (Phase 2: Redis cluster for HA)
4. **Manual Worker Management** — Must start workers manually (Phase 3: Systemd service or Docker)

---

## Success Criteria

✅ Phase 3A is complete when:
- [x] Celery + Redis configured and running
- [x] All three Phase 2 endpoints converted to async tasks
- [x] WebSocket progress updates work in browser
- [x] Progress bar displays correctly on frontend
- [x] Task results retrievable after completion
- [x] Multiple concurrent tasks handled without interference
- [x] Documentation complete
- [x] All tests passing

---

## Timeline

- **Day 1 Morning**: Setup Celery, Redis, task definitions
- **Day 1 Afternoon**: WebSocket integration, testing
- **Day 2 Morning**: Frontend UI updates
- **Day 2 Afternoon**: Integration testing, load testing
- **Day 2 Evening**: Documentation, deployment checklist

---

**Status**: Ready to implement  
**Next**: Set up Celery, Redis, task definitions
