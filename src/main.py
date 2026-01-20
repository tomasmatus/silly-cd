#!/usr/bin/env python3
import argparse
import logging

from podman_cd import PodmanCD
from difftool import DiffTool

logging.basicConfig(level=logging.DEBUG)

def main():
    parser = argparse.ArgumentParser(description='Silly CD')
    parser.add_argument('--repo-dir', type=str, help='Root directory of monitored repository', default=".")
    parser.add_argument('--deploy-dir', type=str, help='Root directory of deployed directory', default=".")

    args = parser.parse_args()

    diffs = DiffTool(args.repo_dir, args.deploy_dir).list_changed_deployments()

    for diff in diffs:
        print(f"{diff.dirname}: {diff.status}")

    # podmanCD = PodmanCD(args.cwd, True)
    # podmanCD.run_update()

if __name__ == "__main__":
    main()
