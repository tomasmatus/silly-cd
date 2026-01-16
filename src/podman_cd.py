import logging
import os
import subprocess

from gitforge import ChangedDir, ChangedFile, DirStatus, FileMap, FileStatus, GitForge
from podman import Podman
from systemctl import Systemctl

logger = logging.getLogger(__name__)

class PodmanCD:
    def __init__(self, work_dir: str, user_mode: bool):
        self.work_dir = work_dir
        self.forge = GitForge(work_dir)
        self.podman = Podman()
        self.systemctl = Systemctl(user_mode=user_mode)

    def run_update(self):
        logger.info("Checking for updates...")

        old_hash = self.forge.latest_commit_hash()
        self.forge.git_pull()
        changed_dirs = self.forge.find_changed_dirs(old_hash, "HEAD")

        if len(changed_dirs) == 0:
            logger.info("No changes detected.")
            return

        self.fetch_new_images(changed_dirs)
        self.handle_services_lifecycle(changed_dirs)

    @staticmethod
    def parse_yaml_for_images(file_name: str) -> set[str]:
        images: set[str] = set()

        with open(file_name, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("image:"):
                    image = line.split("image:")[1].strip()
                    images.add(image)

        return images

    def get_files_endswith(self, dir_name: str, suffix: str | tuple[str, ...]) -> list[str]:
        full_path = f"{self.work_dir}/{dir_name}"
        dir_content = os.listdir(full_path)
        return [f for f in dir_content if f.endswith(suffix)]

    def get_service_name(self, dir: ChangedDir) -> str | None:
        def kube_to_service(name):
            return name.replace(".kube", ".service")

        # try to find it in FileStatus list
        for file in dir.files:
            if file.filename.endswith(".kube"):
                return kube_to_service(file.filename)

        if dir.dir_status == DirStatus.MODIFIED:
            # try to find it in the directory
            try:
                kube_files = self.get_files_endswith(dir.dirname, ".kube")
                if len(kube_files) > 0:
                    return kube_to_service(kube_files[0])
            except FileNotFoundError as e:
                logger.error(f"Unable to find kube file in directory '{dir.dirname}:\n{e}")

        return None

    def fetch_new_images(self, changed_dirs: FileMap):
        images: set[str] = set()
        for dir in changed_dirs.values():
            for file in dir.files:
                if file.filename.endswith((".yaml", ".yml")) and file.status in [FileStatus.ADDED, FileStatus.MODIFIED]:
                    images.union(self.parse_yaml_for_images(f"{dir.dirname}/{file.filename}"))

        for image in images:
            try:
                logger.info(f"Pulling image: {image}")
                self.podman.pull(image)
                logger.info(f"Done pulling: {image}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to pull image {image}")
                raise e

    def modified_service(self, dir: ChangedDir):
        kube_service = self.get_service_name(dir)
        if kube_service == None:
            logger.info(f"Skipping {dir.dirname}")
            return

        logger.info(f"Restarting kube {kube_service}")
        # restart the service, if it is not running it will be started
        self.systemctl.restart(kube_service)

    def deleted_service(self, dir: ChangedDir):
        kube_service = self.get_service_name(dir)
        if kube_service == None:
            logger.info(f"Skipping {dir.dirname}")
            return

        logger.info(f"Stopping deleted kube {kube_service}")
        self.systemctl.stop(kube_service)

    def handle_services_lifecycle(self, changed_dirs: FileMap):
        self.systemctl.daemon_reload()
        for dir in changed_dirs.values():
            if dir.dir_status == DirStatus.MODIFIED:
                self.modified_service(dir)

            elif dir.dir_status == DirStatus.DELETED:
                self.deleted_service(dir)

            else:
                logger.warning(f"Unsupported dir status: {dir.dir_status} for {dir.dirname}, not doing anything!")

