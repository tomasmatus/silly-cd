import logging
import os
import subprocess
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class FileStatus(Enum):
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    UNCHANGED = " "

@dataclass
class DirChangeStatus:
    dir_name: str
    status: FileStatus

    def __hash__(self):
        return hash(self.dir_name)


class GitForge:
    def __init__(self, work_dir: str):
        if not os.path.isdir(work_dir):
            raise FileNotFoundError(f"Directory does not exist: {work_dir}")
        if not os.path.exists(os.path.join(work_dir, '.git')):
            raise FileNotFoundError(f"Not a git repository: {work_dir}")

        self.work_dir = work_dir

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

    def find_changed_dirs(self, commit1: str, commit2: str = "HEAD") -> set[DirChangeStatus]:
        diff_changed = self.git_diff_files_range(commit1, commit2)

        changed_dirs: set[DirChangeStatus] = set()
        if not diff_changed:
            return changed_dirs

        for line in diff_changed.splitlines():
            if not line.strip():
                continue

            parts = line.split("\t", 1)
            if len(parts) != 2:
                logger.warning(f"Unexpected diff output format: '{line}'... ignoring")
                continue

            status_code = parts[0].strip()
            dir_name = os.path.dirname(parts[1].strip())

            if dir_name == "":
                continue

            try:
                status = FileStatus(status_code)
                changed_dirs.add(DirChangeStatus(dir_name=dir_name, status=status))
            except ValueError:
                raise ValueError(f"Unknown dir status: {status_code} for file {dir_name}")

        return changed_dirs
