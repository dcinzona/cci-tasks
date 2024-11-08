# Scan and compare project source directories for duplicate metadata using
# file path and file names, and file API names and labels.
# This script is intended to be run from the command line.
# Usage: python project-scan.py [root_directory]
# If no root directory is provided, the script will run in the current directory.

import os
import json
import sys
from collections import defaultdict

metadata_folders = [
    "aura",
    "classes",
    "components",
    "flexipages",
    "lwc",
    "objects",
    "pages",
    "permissionsets",
    "tabs",
    "triggers",
    "staticresources",
]


class dupeScanner:

    sfdx_project = None
    package_directories = None
    package_directories_path = []
    common_metadata_dir = None
    metadata_paths_per_package = defaultdict(list)
    scanned_files = defaultdict(list)
    root_dir = None
    debug = False

    # get unique entries from duplicate_files
    unique_duplicate_files = defaultdict(list)

    # Special directories (where subfolders replace all components, like LWC)
    special_directories = ["aura", "lwc"]
    files_to_skip = [
        "jsconfig.json",
        ".eslintrc.json",
        "package.xml",
        ".DS_Store",
        ".jsconfig",
    ]

    def __init__(self):
        # get root directory from sys args if provided
        if len(sys.argv) > 1:
            self.root_dir = sys.argv[1]
        else:
            self.root_dir = "."

        os.chdir(self.root_dir)
        # check if sfdx-project.json exists
        if not os.path.exists("sfdx-project.json"):
            print("sfdx-project.json not found in the root directory.")
            exit()

        with open("sfdx-project.json") as f:
            self.sfdx_project = json.load(f)
        self.package_directories = self.sfdx_project["packageDirectories"]
        self.common_metadata_dir = "./common_metadata"
        # get path of each package directory
        for package_directory in self.package_directories:
            self.package_directories_path.append(package_directory["path"])
        self.scan()

    def list_directories(self, path):
        return [
            name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))
        ]

    def getKeyForFilePath(self, filepath) -> str:
        for bundleparent in self.special_directories:
            bundlefolder = "/" + bundleparent + "/"
            if bundlefolder in filepath:
                spl = filepath.split("/")
                filepath = "/".join(spl[:-1])
        return filepath

    def get_duplicate_files(self, metadata_folder, package_path):
        for root, dirs, files in os.walk(metadata_folder):
            # skip if root ends with __tests__
            if "__tests__" in root:
                continue
            # check if file parent is folder with special directories
            for file in files:
                if file in self.files_to_skip:
                    continue
                # if the current directory is a special directory, we only need to
                # check subfolders, not files
                rp = os.path.relpath(root, package_path)
                relative_path = rp.replace(package_path, "")
                file_path = os.path.join(relative_path, file)
                fp = self.getKeyForFilePath(file_path)
                fplst = fp.split("/")
                # get path up to metadata folder
                idx = -2
                for m in metadata_folders:
                    if m in fplst:
                        idx = fplst.index(m)
                        break
                container = "/".join(fplst[:idx])
                file = fp.replace(container, "")
                fullpath = f"{package_path}/{container}{file}"
                log(f"File Path: { (file, fullpath)}", False)

                # add to scanned files if not already in value
                if file not in self.scanned_files.keys():
                    self.scanned_files[file] = [metadata_folder]
                else:
                    if metadata_folder not in self.scanned_files[file]:
                        self.scanned_files[file].append(metadata_folder)

    def scan(self):
        # find all subdirectories within the package directories using os.walk
        # if any of the metadata folders are found, add them to the list of
        # metadata folders to scan
        for package_directory in self.package_directories_path:
            print(f"\nScanning package: {package_directory}")
            for root, dirs, files in os.walk(package_directory):
                for metadata_folder in metadata_folders:
                    if metadata_folder in dirs:
                        pth = os.path.relpath(
                            os.path.join(root, metadata_folder), package_directory
                        )
                        print("- Found metadata folder:", pth)
                        self.metadata_paths_per_package[package_directory].append(pth)

        # check if there are any duplicate filenames within the metadata folders
        # for each metadata folder, find all files
        # if any files have the same name, add them to the list of duplicate files
        print("\nScanning for duplicate files...")
        for package in self.metadata_paths_per_package.keys():
            # print("Scanning Package:", package)
            for metadata_path in self.metadata_paths_per_package[package]:
                dir_to_scan = os.path.join(package, metadata_path)
                (
                    print("...Scanning Metadata Folder:", dir_to_scan)
                    if self.debug
                    else None
                )
                self.get_duplicate_files(dir_to_scan, package)

        for key in self.scanned_files.keys():
            if len(self.scanned_files[key]) > 1:
                self.unique_duplicate_files[key] = self.scanned_files[key]

    def copy_file(self, file_path, new_file_path):
        try:
            if os.path.isdir(file_path):
                os.makedirs(new_file_path, exist_ok=True)
                os.system(f"cp -r {file_path}/* {new_file_path}")
            else:
                os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
                os.system(f'cp "{file_path}" "{new_file_path}"')
        except Exception as e:
            print(f"An error occurred while copying the file: {e}")

    # copy duplicate metadata to a new folder
    # for each duplicate file, copy the file to a new folder
    # the new folder will be named "duplicate_metadata"
    # the file will be copied to a subfolder with the name of the package directory
    # and the metadata folder
    def copy_duplicate_metadata(self):
        # clear the duplicate_metadata folder if it exists
        # if os.path.exists(common_metadata_dir):
        #     os.system(f"mv {common_metadata_dir} {common_metadata_dir}_old")
        for key in self.unique_duplicate_files.keys():
            for package in self.unique_duplicate_files[key]:
                if package == "force-app":
                    continue
                # get the file path
                file_path = os.path.join(package, key)
                # get the new file path
                new_file_path = os.path.join(self.common_metadata_dir, key)
                self.copy_file(file_path, new_file_path)

    def list_files(self, path):
        exclude_files = set(self.files_to_skip)
        return set(
            os.path.relpath(os.path.join(dirpath, file), path)
            for dirpath, dirnames, files in os.walk(path)
            for file in files
            if file not in exclude_files
        )

    def find_unique_in_dir(self, dir1, dir2):
        files_dir1 = self.list_files(dir1)
        files_dir2 = self.list_files(dir2)
        if files_dir1 == files_dir2:
            print(" * Directories are identical")
            return set()

        # check if files in dir2 are not in dir1
        if files_dir1.issuperset(files_dir2):
            print(f" * Files in {dir2} are not in {dir1}")
            return files_dir1.difference(files_dir2)

        print(f" * Files in {dir1} are not in {dir2}")
        return files_dir2.difference(files_dir1)


def log(element, should_log):
    if should_log:
        print(element)


def main():
    checker = dupeScanner()
    files = checker.unique_duplicate_files.keys()
    red = "\033[91m"
    bold = "\033[1m"
    boldred = f"{red}{bold}"
    yellow = "\033[93m"
    boldyellow = f"{yellow}{bold}"
    cyan = "\033[96m"
    end = "\033[0m"
    if len(files) > 0:
        plural = len(files) > 1
        msg = f"Found {boldred}{len(files)}{end} duplicate component{'s' if plural else ''}"
        linebreak = "*" * len(msg)
        print(f"\n{linebreak}\n{msg}\n{linebreak}\n")
        bullet = " \n   - "

        for key in files:
            # get last element of the file path
            files = [
                "/".join(x.split("/")[:-1]) + key
                for x in checker.unique_duplicate_files[key]
            ]
            files = [f"{cyan}{x}{end}" for x in files]
            print(
                f"{boldyellow}{key}{end} was found in {len(files)} places:\n   - {bullet.join(files)}"
            )

    else:
        print("\nNo duplicate files found.")


if __name__ == "__main__":
    main()
