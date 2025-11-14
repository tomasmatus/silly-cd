import logging
import os
import subprocess

from gitforge import DirChangeStatus, FileStatus, GitForge
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
    def parse_yaml_for_images(file_name: str) -> list[str]:
        images: list[str] = []

        with open(file_name, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("image:"):
                    image = line.split("image:")[1].strip()
                    images.append(image)

        return images

    def get_files_endswith(self, dir_name: str, suffix: str | tuple[str, ...]) -> list[str]:
        full_path = f"{self.work_dir}/{dir_name}"
        dir_content = os.listdir(full_path)
        return [f"{full_path}/{f}" for f in dir_content if f.endswith(suffix)]

    def fetch_new_images(self, changed_dirs: list[DirChangeStatus]):
        images: list[str] = []
        for dir_change in changed_dirs:
            if dir_change.status not in [FileStatus.ADDED, FileStatus.MODIFIED]:
                continue

            yamls = self.get_files_endswith(dir_change.dir_name, (".yml", ".yaml"))

            for yaml in yamls:
                images.extend(self.parse_yaml_for_images(yaml))

        for image in images:
            try:
                logger.info(f"Pulling image: {image}")
                self.podman.pull(image)
                logger.info(f"Done pulling: {image}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to pull image {image}")
                raise e

    def handle_services_lifecycle(self , changed_dirs: list[DirChangeStatus]):
        self.systemctl.daemon_reload()
        for dir_change in changed_dirs:
            kube_service = self.get_files_endswith(dir_change.dir_name, (".kube"))
            if len(kube_service) == 0:
                continue
            else:
                kube_service = os.path.basename(kube_service[0].replace(".kube", ".service"))

            if dir_change.status in [FileStatus.ADDED, FileStatus.MODIFIED]:
                logger.info(f"Restarting kube {kube_service}")
                # restart the service, if it is not running it will be started
                self.systemctl.restart(kube_service)

            elif dir_change.status == FileStatus.DELETED:
                self.systemctl.stop(kube_service)

            else:
                logger.warning(f"Unsupported file status: {dir_change.status} for {dir_change.dir_name}, not doing anything!")
