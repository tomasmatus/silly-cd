import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class GitForge:
    def __init__(self, work_dir: Path):
        if not work_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {work_dir}")
        if not os.path.exists(work_dir / ".git"):
            raise FileNotFoundError(f"Not a git repository: {work_dir}")

        self.work_dir = work_dir.resolve()

    def run_git_command(self, *args) -> str:
        """
        Run a git command with the provided arguments.

        Args:
            *args: Git command arguments (e.g., "clone", "pull", "push")

        Returns:
            subprocess.CompletedProcess: The completed process result

        Raises:
            subprocess.CalledProcessError: If the git command fails
        """

        cmd = ["git"] + list(args)
        logging.debug(f"Running git command: {cmd}")

        result = subprocess.run(
            cmd,
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            check=True
        )

        return result.stdout.strip()

    def git_status(self) -> str:
        return self.run_git_command("status", "-v")

    def git_pull(self) -> str:
        return self.run_git_command("pull")

    def git_diff_files_range(self, start_commit: str, end_commit: str) -> str:
        return self.run_git_command("diff", "--name-status", start_commit, end_commit)

    def latest_commit_hash(self) -> str:
        return self.run_git_command("rev-parse", "HEAD")
