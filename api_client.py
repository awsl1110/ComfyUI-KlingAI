import time
import requests
import jwt

BASE_URL = "https://api-beijing.klingai.com"


def encode_jwt_token(ak: str, sk: str, ttl: int = 1800) -> str:
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": ak,
        "exp": int(time.time()) + ttl,
        "nbf": int(time.time()) - 5,
    }
    token = jwt.encode(payload, sk, headers=headers)
    return token if isinstance(token, str) else token.decode()


class KlingClient:
    def __init__(self, access_key: str = "", secret_key: str = "", token: str = ""):
        """Pass either (access_key + secret_key) for auto-refresh JWT,
        or a pre-generated token directly."""
        self._ak = access_key.strip()
        self._sk = secret_key.strip()
        self._static_token = token.strip()
        self._cached_token = ""
        self._token_exp = 0

    def _get_token(self) -> str:
        if self._static_token:
            return self._static_token
        now = int(time.time())
        if not self._cached_token or now >= self._token_exp - 60:
            ttl = 1800
            self._cached_token = encode_jwt_token(self._ak, self._sk, ttl)
            self._token_exp = now + ttl
        return self._cached_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def create_task(self, payload: dict) -> str:
        """POST /v1/videos/omni-video — returns task_id."""
        resp = requests.post(
            f"{BASE_URL}/v1/videos/omni-video",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(
                f"Kling API {resp.status_code}: {resp.text}\n"
                f"Payload: {__import__('json').dumps(payload, ensure_ascii=False)}"
            )
        body = resp.json()
        if body.get("code") != 0:
            raise RuntimeError(f"Kling API error [{body.get('code')}]: {body.get('message')}")
        return body["data"]["task_id"]

    def get_task(self, task_id: str) -> dict:
        """GET /v1/videos/omni-video/{task_id} — returns task data dict."""
        resp = requests.get(
            f"{BASE_URL}/v1/videos/omni-video/{task_id}",
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise RuntimeError(f"Kling API error [{body.get('code')}]: {body.get('message')}")
        return body["data"]

    def wait(self, task_id: str, timeout: int = 600, interval: int = 5) -> dict:
        """Block until task_status == 'succeed'. Returns task data."""
        deadline = time.time() + timeout
        dots = 0
        while time.time() < deadline:
            task = self.get_task(task_id)
            status = task.get("task_status", "")
            print(
                f"\r[KlingAI] task={task_id[:8]}… status={status} {'.' * (dots % 4 + 1)}   ",
                end="",
                flush=True,
            )
            dots += 1
            if status == "succeed":
                print()
                return task
            if status == "failed":
                print()
                raise RuntimeError(
                    f"Task {task_id} failed: {task.get('task_status_msg', 'unknown')}"
                )
            time.sleep(interval)
        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
