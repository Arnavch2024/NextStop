from typing import Any, Dict, List
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app.agent.runner import get_gemini_client
from app.db.supabase import get_supabase_client
from app.main import app
from app.models.db import ProfileRole, UserProfile


class FakeQueryBuilder:
    def __init__(self, table_name: str, store: Dict[str, List[Dict[str, Any]]]):
        self.table_name = table_name
        self.store = store
        self._action = "select"
        self._filters = []
        self._payload = None

    def select(self, fields: str = "*"):
        self._action = "select"
        return self

    def insert(self, data: Any):
        self._action = "insert"
        self._payload = data if isinstance(data, list) else [data]
        return self

    def update(self, data: Any):
        self._action = "update"
        self._payload = data
        return self

    def eq(self, column: str, value: Any):
        self._filters.append(lambda row: str(row.get(column)) == str(value))
        return self

    def ilike(self, column: str, value: Any):
        self._filters.append(lambda row: str(row.get(column, "")).lower() == str(value).lower())
        return self

    def limit(self, count: int):
        return self

    def order(self, column: str, desc: bool = False):
        return self

    def execute(self):
        rows = self.store.setdefault(self.table_name, [])

        if self._action == "select":
            res = rows
            for f in self._filters:
                res = [r for r in res if f(r)]
            mock_res = MagicMock()
            mock_res.data = [dict(r) for r in res]
            return mock_res

        elif self._action == "insert":
            created = []
            for item in self._payload:
                new_row = dict(item)
                if "id" not in new_row:
                    import uuid
                    new_row["id"] = str(uuid.uuid4())
                rows.append(new_row)
                created.append(new_row)
            mock_res = MagicMock()
            mock_res.data = created
            return mock_res

        elif self._action == "update":
            updated = []
            for r in rows:
                if all(f(r) for f in self._filters):
                    r.update(self._payload)
                    updated.append(dict(r))
            mock_res = MagicMock()
            mock_res.data = updated
            return mock_res

        mock_res = MagicMock()
        mock_res.data = []
        return mock_res


class FakeStorageBucket:
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.files = {}

    def upload(self, path: str, file_bytes: Any, file_options: Any = None):
        self.files[path] = file_bytes
        return {"Key": f"{self.bucket_name}/{path}"}

    def create_signed_url(self, path: str, expires_in: int = 3600):
        return {"signedURL": f"https://mock-storage.local/{self.bucket_name}/{path}?token=mock-token"}


class FakeStorageClient:
    def __init__(self):
        self.buckets = {}

    def from_(self, bucket_name: str):
        if bucket_name not in self.buckets:
            self.buckets[bucket_name] = FakeStorageBucket(bucket_name)
        return self.buckets[bucket_name]


class MockSupabaseClient:
    def __init__(self):
        self.store: Dict[str, List[Dict[str, Any]]] = {
            "profiles": [
                {
                    "id": "user-123",
                    "role": "student",
                    "display_name": "Riya Sharma",
                },
                {
                    "id": "recruiter-456",
                    "role": "recruiter",
                    "display_name": "Karan Mehta",
                },
            ],
            "students": [],
            "colleges": [],
            "companies": [],
            "contacts": [],
            "raw_events": [],
            "agent_runs": [],
            "education": [],
            "internships": [],
            "jobs": [],
            "skills": [],
            "documents": [],
            "score_events": [],
        }
        self.auth = MagicMock()
        self.auth.get_user.side_effect = self._mock_get_user
        self.storage = FakeStorageClient()

    def _mock_get_user(self, token: str):
        if token == "valid-token-student":
            user_obj = MagicMock()
            user_obj.id = "user-123"
            user_obj.email = "riya@example.com"
            user_obj.user_metadata = {"full_name": "Riya Sharma"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-recruiter":
            user_obj = MagicMock()
            user_obj.id = "recruiter-456"
            user_obj.email = "karan@example.com"
            user_obj.user_metadata = {"full_name": "Karan Mehta"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        else:
            raise Exception("Invalid JWT token")

    def table(self, name: str):
        return FakeQueryBuilder(name, self.store)


@pytest.fixture
def mock_supabase():
    return MockSupabaseClient()


@pytest.fixture
def client(mock_supabase):
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

