import logging
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class FileStatus(Enum):
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    UNCHANGED = " "

class DirStatus(Enum):
    UNDEFINED = "UNDEFINED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"

@dataclass
class ChangedFile:
    filename: str
    status: FileStatus

@dataclass
class ChangedDir:
    dirname: str
    files: list[ChangedFile] = field(default_factory=list)
    dir_status: DirStatus = DirStatus.UNDEFINED

    def __assess_status(self):
        if all(file.status == FileStatus.DELETED for file in self.files):
            self.dir_status = DirStatus.DELETED
            return

        self.dir_status = DirStatus.MODIFIED

class FileMap(dict[str, ChangedDir]):
    def __missing__(self, key: str) -> ChangedDir:
        new_dir = ChangedDir(dirname=key)
        self[key] = new_dir
        return new_dir

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

    def find_changed_dirs(self, commit1: str, commit2: str = "HEAD") -> FileMap:
        diff_changed = self.git_diff_files_range(commit1, commit2)

        changed_dirs = FileMap()
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
            dirname = os.path.dirname(parts[1].strip())
            filename = os.path.basename(parts[1].strip())

            if dirname == "":
                continue

            try:
                status = FileStatus(status_code)
                changed_dirs[dirname].files.append(ChangedFile(filename=filename, status=status))
            except ValueError:
                raise ValueError(f"Unknown file status: {status_code} for file {dirname}/{filename}")

        for dir in changed_dirs.values():
            dir.__assess_status()

        return changed_dirs
