from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_anon_client, get_supabase_client
from app.main import app


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

    def upsert(self, data: Any, on_conflict: Optional[str] = None):
        self._action = "upsert"
        self._payload = data if isinstance(data, list) else [data]
        self._on_conflict = on_conflict
        return self

    def update(self, data: Any):
        self._action = "update"
        self._payload = data
        return self

    def eq(self, column: str, value: Any):
        self._filters.append(lambda row: str(row.get(column)) == str(value))
        return self

    def neq(self, column: str, value: Any):
        self._filters.append(lambda row: str(row.get(column)) != str(value))
        return self

    def is_(self, column: str, value: Any):
        if value is None or str(value).lower() in ("null", "none"):
            self._filters.append(lambda row: row.get(column) is None)
        else:
            self._filters.append(lambda row: row.get(column) == value)
        return self

    def in_(self, column: str, values: List[Any]):
        self._filters.append(lambda row: row.get(column) in values)
        return self

    def gte(self, column: str, value: Any):
        self._filters.append(lambda row: row.get(column) is not None and str(row.get(column)) >= str(value))
        return self

    def lte(self, column: str, value: Any):
        self._filters.append(lambda row: row.get(column) is not None and str(row.get(column)) <= str(value))
        return self

    def ilike(self, column: str, value: Any):
        self._filters.append(lambda row: str(value).lower().replace("%", "") in str(row.get(column, "")).lower())
        return self

    def delete(self):
        self._action = "delete"
        return self

    def maybe_single(self):
        return self

    def single(self):
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def range(self, start: int, end: int):
        self._range = (start, end)
        return self

    def order(self, column: str, desc: bool = False):
        return self

    def execute(self):
        rows = self.store.setdefault(self.table_name, [])

        if self._action == "select":
            res = rows
            for f in self._filters:
                res = [r for r in res if f(r)]
            if hasattr(self, "_range") and self._range:
                res = res[self._range[0] : self._range[1] + 1]
            elif hasattr(self, "_limit") and self._limit:
                res = res[: self._limit]
            mock_res = MagicMock()
            mock_res.data = [dict(r) for r in res]
            mock_res.count = len(res)
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

        elif self._action == "upsert":
            created_or_updated = []
            on_conf = getattr(self, "_on_conflict", None)
            for item in self._payload:
                new_row = dict(item)
                matched = False
                if on_conf:
                    for r in rows:
                        if r.get(on_conf) == new_row.get(on_conf):
                            r.update(new_row)
                            created_or_updated.append(r)
                            matched = True
                            break
                if not matched:
                    if "id" not in new_row:
                        import uuid

                        new_row["id"] = str(uuid.uuid4())
                    rows.append(new_row)
                    created_or_updated.append(new_row)
            mock_res = MagicMock()
            mock_res.data = created_or_updated
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

        elif self._action == "delete":
            deleted = []
            remaining = []
            for r in rows:
                if all(f(r) for f in self._filters):
                    deleted.append(dict(r))
                else:
                    remaining.append(r)
            self.store[self.table_name] = remaining
            mock_res = MagicMock()
            mock_res.data = deleted
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
                    "is_demo": False,
                },
                {
                    "id": "recruiter-456",
                    "role": "recruiter",
                    "display_name": "Karan Mehta",
                    "is_demo": False,
                },
                {
                    "id": "officer-789",
                    "role": "placement_officer",
                    "display_name": "Placement Officer",
                    "college_id": "col-mumbai-1",
                    "is_demo": False,
                },
                {
                    "id": "company-999",
                    "role": "company",
                    "display_name": "Company HR",
                    "company_id": "comp-tcs-1",
                    "is_demo": False,
                },
                {
                    "id": "demo-officer-id",
                    "role": "placement_officer",
                    "display_name": "Prof. Sunita Patil",
                    "email": "demo-officer@example.com",
                    "college_id": "col-mumbai-1",
                    "is_demo": True,
                },
                {
                    "id": "demo-company-id",
                    "role": "company",
                    "display_name": "Pooja Sharma",
                    "email": "demo-company@example.com",
                    "company_id": "comp-tcs-1",
                    "is_demo": True,
                },
                {
                    "id": "demo-recruiter-id",
                    "role": "recruiter",
                    "display_name": "Karan Mehta",
                    "email": "demo-recruiter@example.com",
                    "is_demo": True,
                },
                {
                    "id": "demo-student-id",
                    "role": "student",
                    "display_name": "Riya Sharma",
                    "email": "demo-student@example.com",
                    "college_id": "col-mumbai-1",
                    "is_demo": True,
                },
                {
                    "id": "user-null-role",
                    "role": None,
                    "display_name": "New User",
                    "email": "newuser@example.com",
                    "is_demo": False,
                },
                {
                    "id": "user-vjti-student",
                    "role": None,
                    "display_name": "Rahul VJTI",
                    "email": "rahul@vjti.ac.in",
                    "is_demo": False,
                },
                {
                    "id": "user-gmail-student",
                    "role": None,
                    "display_name": "Rahul Gmail",
                    "email": "rahul@gmail.com",
                    "is_demo": False,
                },
                {
                    "id": "user-company-domain",
                    "role": None,
                    "display_name": "TCS HR",
                    "email": "hr@tcs.com",
                    "is_demo": False,
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
            "contact_sources": [],
            "search_cache": [],
            "user_saved_contacts": [],
            "outreach_drafts": [],
            "student_records": [],
            "campus_hiring": [],
            "batch_sharing": [],
            "college_domains": [],
        }
        self.auth = MagicMock()
        self.auth.get_user.side_effect = self._mock_get_user
        self.auth.sign_in_with_password.side_effect = self._mock_sign_in_with_password
        self.storage = FakeStorageClient()

    def _mock_sign_in_with_password(self, credentials: dict):
        email = credentials.get("email")
        if email in ["demo-officer@example.com", "placement.officer@stxaviers.edu"]:
            session = MagicMock()
            session.access_token = "valid-token-demo-officer"
            session.refresh_token = "valid-refresh-demo-officer"
            session.expires_at = 1999999999
            user = MagicMock()
            user.id = "demo-officer-id"
            user.email = email
            resp = MagicMock()
            resp.session = session
            resp.user = user
            return resp
        elif email in ["demo-company@example.com", "pooja.sharma@tcs.com"]:
            session = MagicMock()
            session.access_token = "valid-token-demo-company"
            session.refresh_token = "valid-refresh-demo-company"
            session.expires_at = 1999999999
            user = MagicMock()
            user.id = "demo-company-id"
            user.email = email
            resp = MagicMock()
            resp.session = session
            resp.user = user
            return resp
        elif email in ["demo-recruiter@example.com", "karan.recruiter@apexsearch.com"]:
            session = MagicMock()
            session.access_token = "valid-token-demo-recruiter"
            session.refresh_token = "valid-refresh-demo-recruiter"
            session.expires_at = 1999999999
            user = MagicMock()
            user.id = "demo-recruiter-id"
            user.email = email
            resp = MagicMock()
            resp.session = session
            resp.user = user
            return resp
        elif email in ["demo-student@example.com", "riya.sharma@stxaviers.edu"]:
            session = MagicMock()
            session.access_token = "valid-token-demo-student"
            session.refresh_token = "valid-refresh-demo-student"
            session.expires_at = 1999999999
            user = MagicMock()
            user.id = "demo-student-id"
            user.email = email
            resp = MagicMock()
            resp.session = session
            resp.user = user
            return resp
        else:
            raise Exception("Invalid login credentials")

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
        elif token == "valid-token-officer":
            user_obj = MagicMock()
            user_obj.id = "officer-789"
            user_obj.email = "officer@college.edu"
            user_obj.user_metadata = {"full_name": "Placement Officer"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-company":
            user_obj = MagicMock()
            user_obj.id = "company-999"
            user_obj.email = "hr@company.com"
            user_obj.user_metadata = {"full_name": "Company HR"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-demo-officer":
            user_obj = MagicMock()
            user_obj.id = "demo-officer-id"
            user_obj.email = "demo-officer@example.com"
            user_obj.user_metadata = {"full_name": "Prof. Sunita Patil", "is_demo": True}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-demo-company":
            user_obj = MagicMock()
            user_obj.id = "demo-company-id"
            user_obj.email = "demo-company@example.com"
            user_obj.user_metadata = {"full_name": "Pooja Sharma", "is_demo": True}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-demo-recruiter":
            user_obj = MagicMock()
            user_obj.id = "demo-recruiter-id"
            user_obj.email = "demo-recruiter@example.com"
            user_obj.user_metadata = {"full_name": "Karan Mehta", "is_demo": True}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-demo-student":
            user_obj = MagicMock()
            user_obj.id = "demo-student-id"
            user_obj.email = "demo-student@example.com"
            user_obj.user_metadata = {"full_name": "Riya Sharma", "is_demo": True}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-null-role":
            user_obj = MagicMock()
            user_obj.id = "user-null-role"
            user_obj.email = "newuser@example.com"
            user_obj.user_metadata = {"full_name": "New User"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-college-student":
            user_obj = MagicMock()
            user_obj.id = "user-vjti-student"
            user_obj.email = "rahul@vjti.ac.in"
            user_obj.user_metadata = {"full_name": "Rahul VJTI"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-gmail-student":
            user_obj = MagicMock()
            user_obj.id = "user-gmail-student"
            user_obj.email = "rahul@gmail.com"
            user_obj.user_metadata = {"full_name": "Rahul Gmail"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        elif token == "valid-token-company-user":
            user_obj = MagicMock()
            user_obj.id = "user-company-domain"
            user_obj.email = "hr@tcs.com"
            user_obj.user_metadata = {"full_name": "TCS HR"}
            resp = MagicMock()
            resp.user = user_obj
            return resp
        else:
            raise Exception("Invalid JWT token")

    def table(self, name: str):
        return FakeQueryBuilder(name, self.store)


@pytest.fixture(autouse=True)
def default_demo_show_sample(monkeypatch):
    """Enables DEMO_SHOW_SAMPLE and SKIP_SCHEMA_CHECK by default for mock tests."""
    monkeypatch.setenv("DEMO_SHOW_SAMPLE", "true")
    monkeypatch.setenv("SKIP_SCHEMA_CHECK", "true")


@pytest.fixture
def mock_supabase():
    return MockSupabaseClient()


@pytest.fixture
def client(mock_supabase):
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase
    app.dependency_overrides[get_anon_client] = lambda: mock_supabase
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
