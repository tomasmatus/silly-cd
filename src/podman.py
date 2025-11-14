import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)


class Podman:
    def __init__(self):
        pass

    def run_podman_command(self, *args) -> str:
        """
        Run a podman command with the provided arguments.

        Args:
            *args: Podman command arguments (e.g., "ps", "run", "build")

        Returns:
            str: The stdout output of the command

        Raises:
            subprocess.CalledProcessError: If the podman command fails
        """
        cmd = ["podman"] + list(args)
        logger.debug(f"Running podman command: {cmd}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        return result.stdout.strip()

    def pull(self, image: str) -> str:
        return self.run_podman_command("pull", image)
