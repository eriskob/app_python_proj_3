from locust import HttpUser, between, task
import random


SHORT_CODES = [
    "abc123",
    "def456",
    "ghi789",
    "jkl012",
    "mno345",
    "pqr678",
    "stu901",
    "vwx234",
]


class ShortenerUser(HttpUser):
    wait_time = between(0.001, 0.01)

    @task(10)
    def get_stats(self):
        short_code = random.choice(SHORT_CODES)
        self.client.get(
            f"/links/{short_code}/stats",
            name="GET /links/{short_code}/stats",
        )

    @task(10)
    def redirect(self):
        short_code = random.choice(SHORT_CODES)
        self.client.get(
            f"/links/{short_code}",
            name="GET /links/{short_code}",
            allow_redirects=False,
        )