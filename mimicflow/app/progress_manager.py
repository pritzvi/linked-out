# mimicflow/app/progress_manager.py
from typing import Dict, List, Optional
from pydantic import BaseModel
import asyncio


class Profile(BaseModel):
    id: str
    name: str = ""
    url: str = ""
    status: str = "pending"
    message: str = ""


class ProgressManager:
    def __init__(self):
        self.profiles: List[Profile] = []
        self.is_done: bool = False
        self.profiles_needed: int = 0
        self._lock = asyncio.Lock()
        self.csv_file_path: Optional[str] = None  # Add this line

    async def reset(self):
        async with self._lock:
            self.profiles = []
            self.is_done = False
            self.profiles_needed = 0

    async def set_target(self, count: int):
        async with self._lock:
            self.profiles_needed = count

    async def add_profile(self, profile: Dict):
        async with self._lock:
            new_profile = Profile(
                id=str(len(self.profiles) + 1),
                name=profile.get("name", ""),
                url=profile.get("URL", ""),
                status="pending",
                message="Profile discovered",
            )
            self.profiles.append(new_profile)
            return new_profile.id

    async def update_profile(self, profile_id: str, **kwargs):
        async with self._lock:
            for profile in self.profiles:
                if profile.id == profile_id:
                    for key, value in kwargs.items():
                        setattr(profile, key, value)
                    break

    async def mark_done(self):
        async with self._lock:
            self.is_done = True

    async def set_csv_file_path(self, path: str):
        async with self._lock:
            self.csv_file_path = path

    async def get_state(self):
        async with self._lock:
            return {
                "profiles": [p.dict() for p in self.profiles],
                "is_done": self.is_done,
                "profiles_needed": self.profiles_needed,
                "csv_file_path": self.csv_file_path
                if self.csv_file_path
                else None,  # Add this line
            }
