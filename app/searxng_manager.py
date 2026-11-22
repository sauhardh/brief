import os
import shutil
import subprocess
import time
import requests
import logging

log = logging.getLogger(__name__)

SEARXNG_PORT = int(os.getenv("SEARXNG_PORT", "8080"))
SEARXNG_URL = os.getenv("SEARXNG_URL", f"http://localhost:{SEARXNG_PORT}")
CONTAINER_NAME = "searxng-brief"


def is_searxng_ready(url: str = SEARXNG_URL, timeout: float = 2.0) -> bool:
    try:
        res = requests.get(f"{url}/search?q=ping&format=json", timeout=timeout)
        if res.status_code == 200:
            return True
    except Exception:
        pass
    return False


def ensure_searxng_running() -> str | None:
    # 1. Fast path: check if already running and responding
    if is_searxng_ready(SEARXNG_URL, timeout=1.5):
        log.info(f"Local SearXNG instance is ready at {SEARXNG_URL}")
        return SEARXNG_URL

    # 2. Check if Docker CLI is installed
    if not shutil.which("docker"):
        log.info(
            "Docker command not found on system. Skipping local SearXNG container."
        )
        return None

    # 3. Ensure configuration directory and settings.yml exist
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(base_dir, "searxng_config")
    os.makedirs(config_dir, exist_ok=True)
    settings_file = os.path.join(config_dir, "settings.yml")

    if not os.path.exists(settings_file):
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write(
                "use_default_settings: true\n"
                "server:\n"
                "  secret_key: 'brief_searxng_local_secret_key_random'\n"
                "search:\n"
                "  formats:\n"
                "    - html\n"
                "    - json\n"
            )

    # 4. Check if container already exists
    try:
        check = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name=^/{CONTAINER_NAME}$",
                "--format",
                "{{.Names}} {{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = check.stdout.strip()

        if CONTAINER_NAME in output:
            if "Up" not in output:
                log.info(f"Starting stopped '{CONTAINER_NAME}' Docker container...")
                subprocess.run(
                    ["docker", "start", CONTAINER_NAME],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
        else:
            log.info(
                f"Creating and starting new '{CONTAINER_NAME}' Docker container on port {SEARXNG_PORT}..."
            )
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    CONTAINER_NAME,
                    "-p",
                    f"{SEARXNG_PORT}:8080",
                    "-v",
                    f"{settings_file}:/etc/searxng/settings.yml:ro",
                    "searxng/searxng",
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )

        # 5. Wait up to 10 seconds for SearXNG to boot and pass readiness probe
        log.info("Waiting for SearXNG container to be ready...")
        for _ in range(10):
            time.sleep(1)
            if is_searxng_ready(SEARXNG_URL, timeout=1.5):
                log.info(f"SearXNG container is ready and responsive at {SEARXNG_URL}")
                return SEARXNG_URL

        log.warning(
            "SearXNG container started but timed out waiting for JSON readiness probe."
        )
    except Exception as e:
        log.warning(f"Could not auto-start SearXNG Docker container: {e}")

    return None
