from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class ModificationStatus(Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"

@dataclass
class DeploymentStatus:
    path: Path
    status: ModificationStatus
    service_name: str | None

class DiffTool:
    desired_dir: Path
    deployed_dir: Path

    def __init__(self, desired_dir: Path, deployed_dir: Path) -> None:
        self.desired_dir = desired_dir
        self.deployed_dir = deployed_dir

        if (self.desired_dir.exists() is False) or (self.desired_dir.is_dir() is False):
            raise NotADirectoryError(f"Desired directory does not exist or is not a directory: {self.desired_dir}")
        if (self.deployed_dir.exists() is False) or (self.deployed_dir.is_dir() is False):
            raise NotADirectoryError(f"deployed directory does not exist or is not a directory: {self.deployed_dir}")

    @staticmethod
    def _file_condition(file: Path) -> bool:
        """
            Only consider regular files that are not hidden.
        """
        return file.is_file() and not file.name.startswith(".")

    @staticmethod
    def _dir_condition(file: Path) -> bool:
        """
            Only consider directories that are not hidden.
        """
        return file.is_dir() and not file.name.startswith(".")

    @staticmethod
    def get_service_name(dir: Path) -> str | None:
        for file in dir.iterdir():
            if file.is_file() and file.suffix == ".kube":
                return file.stem + ".service"

        return None

    def _check_modification(self, dirs: set[Path]) -> list[DeploymentStatus]:
        result: list[DeploymentStatus] = []
        for desired_subdir in dirs:
            deployed_subdir = self.deployed_dir / desired_subdir.name

            # Get all files recursively in both subdirectories (using relative paths)
            desired_files = {f.relative_to(desired_subdir) for f in desired_subdir.rglob('*') if self._file_condition(f)}
            deployed_files = {f.relative_to(deployed_subdir) for f in deployed_subdir.rglob('*') if self._file_condition(f)}

            # Check for added or deleted files
            added_files = desired_files - deployed_files
            deleted_files = deployed_files - desired_files

            # Check for modified files (files that exist in both)
            common_files = desired_files.intersection(deployed_files)

            modified_files = set()
            for file in common_files:
                desired_file = desired_subdir / file
                deployed_file = deployed_subdir / file
                # Compare file contents
                if desired_file.read_bytes() != deployed_file.read_bytes():
                    modified_files.add(file)

            # Determine status
            if added_files or deleted_files or modified_files:
                result.append(DeploymentStatus(desired_subdir, ModificationStatus.MODIFIED, self.get_service_name(desired_subdir)))

        return result

    def list_deployment_differences(self) -> list[DeploymentStatus]:
        """
            List modifications on top level subdirectories in deployed state
        """
        desired_subdirs = set(f for f in self.desired_dir.iterdir() if self._dir_condition(f))
        deployed_subdirs = set(f for f in self.deployed_dir.iterdir() if self._dir_condition(f))

        deleted_dirs = deployed_subdirs - desired_subdirs
        added_dirs = desired_subdirs - deployed_subdirs
        other_dirs = desired_subdirs.intersection(deployed_subdirs)

        dir_status = [DeploymentStatus(dir, ModificationStatus.DELETED, self.get_service_name(dir)) for dir in deleted_dirs]
        dir_status.extend([DeploymentStatus(dir, ModificationStatus.ADDED, self.get_service_name(dir)) for dir in added_dirs])
        dir_status.extend(self._check_modification(other_dirs))

        return dir_status
