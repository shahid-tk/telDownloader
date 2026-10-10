import asyncio
import time
from typing import Dict, List, Optional
from pydantic import BaseModel


class DownloadTask(BaseModel):
    id: str
    name: str
    media_type: str = "unknown"  # movie / show
    size: int = 0
    downloaded_bytes: int = 0
    percent: int = 0
    speed_str: str = "0 KB/s"
    eta_str: str = "--"
    status: str = "downloading"  # downloading, processing, completed, failed
    error_message: Optional[str] = None
    started_at: float = 0.0
    completed_at: Optional[float] = None


class DownloadTracker:
    def __init__(self):
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.history: List[DownloadTask] = []
        self._listeners: List[asyncio.Queue] = []

    def start_download(self, task_id: str, name: str, media_type: str, size: int) -> DownloadTask:
        task = DownloadTask(
            id=task_id,
            name=name,
            media_type=media_type,
            size=size or 0,
            started_at=time.time(),
            status="downloading",
        )
        self.active_tasks[task_id] = task
        self.notify_change()
        return task

    def update_progress(
        self,
        task_id: str,
        downloaded: int,
        total: int,
        percent: int,
        speed_str: str,
        eta_str: str,
    ) -> None:
        task = self.active_tasks.get(task_id)
        if not task:
            return
        task.downloaded_bytes = downloaded
        if total > 0:
            task.size = total
        task.percent = percent
        task.speed_str = speed_str
        task.eta_str = eta_str
        self.notify_change()

    def set_status(self, task_id: str, status: str, error_msg: Optional[str] = None) -> None:
        task = self.active_tasks.get(task_id)
        if not task:
            return
        task.status = status
        task.error_message = error_msg
        if status in ("completed", "failed"):
            task.completed_at = time.time()
            self.history.insert(0, task)
            if len(self.history) > 50:
                self.history.pop()
            self.active_tasks.pop(task_id, None)
        self.notify_change()

    def get_all(self) -> dict:
        return {
            "active": [t.model_dump() for t in self.active_tasks.values()],
            "history": [t.model_dump() for t in self.history[:15]],
        }

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    def notify_change(self) -> None:
        data = self.get_all()
        for q in list(self._listeners):
            try:
                q.put_nowait(data)
            except Exception:
                pass


# Global singleton instance
tracker = DownloadTracker()
