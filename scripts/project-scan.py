# Scan and compare project source directories for duplicate metadata using
# file path and file names, and file API names and labels.
# This script is intended to be run from the command line.
# Usage: python project-scan.py

import os
import json
from collections import defaultdict

# Read sfdx-project.json to get the package directories
sfdx_project = None
with open("sfdx-project.json") as f:
    sfdx_project = json.load(f)
package_directories = sfdx_project["packageDirectories"]
common_metadata_dir = "./common_metadata"

# get path of each package directory
package_directories_path = []
for package_directory in package_directories:
    package_directories_path.append(package_directory["path"])

print("Scanning packages: ", ", ".join(package_directories_path))

# Set metadata folders within package directories to scan
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


def list_directories(path):
    return [
        name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))
    ]


for package_directory in package_directories_path:
    # print("Scanning package:", package_directory)
    # check if folder structure = main/default
    if "main" in list_directories(package_directory):
        # print("  Found main folder")
        package_directory = os.path.join(package_directory, "main", "default")
        for folder in list_directories(package_directory):
            metadata_folders.append(folder)
    else:
        print("  No main folder found")

# trim string to remove leading and trailing whitespace
metadata_folders = [x.strip() for x in metadata_folders]
metadata_folders = list(set(metadata_folders))
metadata_folders.sort()

print("Metadata folders to scan:\n -", ",\n - ".join(metadata_folders))


# Special directories (where subfolders replace all components, like LWC)
special_directories = ["aura", "lwc"]
files_to_skip = ["jsconfig.json", ".eslintrc.json", "package.xml", ".DS_Store"]

# find all subdirectories within the package directories using os.walk
# if any of the metadata folders are found, add them to the list of
# metadata folders to scan
metadata_paths_per_package = defaultdict(list)
for package_directory in package_directories_path:
    for root, dirs, files in os.walk(package_directory):
        for metadata_folder in metadata_folders:
            if metadata_folder in dirs:
                pth = os.path.relpath(
                    os.path.join(root, metadata_folder), package_directory
                )
                metadata_paths_per_package[package_directory].append(pth)

# check if there are any duplicate filenames within the metadata folders
# for each metadata folder, find all files
# if any files have the same name, add them to the list of duplicate files
scanned_files = defaultdict(list)


def getKeyForFilePath(filepath) -> str:
    for bundleparent in special_directories:
        bundlefolder = "/" + bundleparent + "/"
        if bundlefolder in filepath:
            spl = filepath.split("/")
            filepath = "/".join(spl[:-1])
    return filepath


def get_duplicate_files(metadata_folder, package_path):
    for root, dirs, files in os.walk(metadata_folder):
        # skip if root ends with __tests__
        if "__tests__" in root:
            continue
        # check if file parent is folder with special directories
        for file in files:
            if file in files_to_skip:
                continue
            # if the current directory is a special directory, we only need to
            # check subfolders, not files
            rp = os.path.relpath(root, package_path)
            relative_path = rp.replace(package_path, "")
            file_path = os.path.join(relative_path, file)
            fp = getKeyForFilePath(file_path)
            # add to scanned files if not already in value
            if fp not in scanned_files.keys():
                scanned_files[fp] = [package_path]
            else:
                if package_path not in scanned_files[fp]:
                    scanned_files[fp].append(package_path)


for package in metadata_paths_per_package.keys():
    # print("Scanning Package:", package)
    for metadata_path in metadata_paths_per_package[package]:
        dir_to_scan = os.path.join(package, metadata_path)
        get_duplicate_files(dir_to_scan, package)


# get unique entries from duplicate_files
unique_duplicate_files = defaultdict(list)

for key in scanned_files.keys():
    if len(scanned_files[key]) > 1:
        unique_duplicate_files[key] = scanned_files[key]


def copy_file(file_path, new_file_path):
    try:
        if os.path.isdir(file_path):
            os.makedirs(new_file_path, exist_ok=True)
            os.system(f"mv -r {file_path}/* {new_file_path}")
        else:
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
            os.system(f'mv "{file_path}" "{new_file_path}"')
    except Exception as e:
        print(f"An error occurred while copying the file: {e}")


# copy duplicate metadata to a new folder
# for each duplicate file, copy the file to a new folder
# the new folder will be named "duplicate_metadata"
# the file will be copied to a subfolder with the name of the package directory
# and the metadata folder
def copy_duplicate_metadata():
    # clear the duplicate_metadata folder if it exists
    # if os.path.exists(common_metadata_dir):
    #     os.system(f"mv {common_metadata_dir} {common_metadata_dir}_old")
    for key in unique_duplicate_files.keys():
        for package in unique_duplicate_files[key]:
            if package == "force-app":
                continue
            # get the file path
            file_path = os.path.join(package, key)
            # get the new file path
            new_file_path = os.path.join(common_metadata_dir, key)
            copy_file(file_path, new_file_path)


def list_files(path):
    exclude_files = set(files_to_skip)
    return set(
        os.path.relpath(os.path.join(dirpath, file), path)
        for dirpath, dirnames, files in os.walk(path)
        for file in files
        if file not in exclude_files
    )


def find_unique_in_dir(dir1, dir2):
    files_dir1 = list_files(dir1)
    files_dir2 = list_files(dir2)
    if files_dir1 == files_dir2:
        print(" * Directories are identical")
        return set()

    # check if files in dir2 are not in dir1
    if files_dir1.issuperset(files_dir2):
        print(f" * Files in {dir2} are not in {dir1}")
        return files_dir1.difference(files_dir2)

    print(f" * Files in {dir1} are not in {dir2}")
    return files_dir2.difference(files_dir1)


# usage
copy_duplicate_metadata()
# replace main/default/ with empty string
list_of_duplicates = [
    x.replace("main/default/", "") for x in list_files(common_metadata_dir)
]
if len(list_of_duplicates) == 0:
    print("\nNo duplicate files found.")
    exit()
print("\n\nDuplicate Metadata folder contents:\n")
list_of_duplicates.sort()
for file in list_of_duplicates:
    print(f" - {file}")
