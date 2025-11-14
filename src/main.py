#!/usr/bin/env python3
import argparse
import logging

from gitforge import GitForge

logging.basicConfig(level=logging.DEBUG)

def main():
    parser = argparse.ArgumentParser(description='Silly CD')
    parser.add_argument('--cwd', type=str, help='Root directory of monitored repository', default=".")

    args = parser.parse_args()

    forge = GitForge(args.cwd)
    changes = forge.find_changed_files("8c6c8e4b699919be6ef987a32e624304f24085e3", "HEAD")

    for c in changes:
        print(f"File: {c.file_name}, Status: {c.status.name}")


if __name__ == "__main__":
    main()
