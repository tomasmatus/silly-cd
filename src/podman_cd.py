import logging
import os
import subprocess

from gitforge import DirChangeStatus, FileStatus, GitForge
from podman import Podman

logger = logging.getLogger(__name__)

class PodmanCD:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.forge = GitForge(work_dir)
        self.podman = Podman()

    def check_for_updates(self):
        logger.info("Checking for updates...")

        old_hash = self.forge.latest_commit_hash()
        self.forge.git_pull()
        changed_files = self.forge.find_changed_dirs(old_hash, "HEAD")

        if len(changed_files) == 0:
            logger.info("No changes detected.")
            return

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
        dir_content = os.listdir(dir_name)
        return [f"{self.work_dir}/{dir_name}/{f}" for f in dir_content if f.endswith(suffix)]

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
                self.podman.podman_pull(image)
                logger.info(f"Done pulling: {image}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to pull image {image}")
                raise e

    def handle_services_lifecycle(self , changed_dirs: list[DirChangeStatus]):
        for dir_change in changed_dirs:
            kube_service = self.get_files_endswith(dir_change.dir_name, (".kube"))
            if len(kube_service) == 0:
                continue
            else:
                kube_service = kube_service[0].replace(".kube", ".service")

            if dir_change.status in [FileStatus.ADDED, FileStatus.MODIFIED]:
                logger.info(f"Restarting kube {kube_service}")
                # systemctl --user restart kube_service

            elif dir_change.status == FileStatus.DELETED:
                pass
                # systemctl --user stop kube_service

            else:
                logger.warning(f"Unsupported file status: {dir_change.status} for {dir_change.dir_name}, not doing anything!")
