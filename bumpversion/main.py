import os
import json

# modify project_dir to the full path of your project directory
project_dir = ""

package_contents = ''
package_lock_contents = ''

# warn user
print("This script will checkout the master branch. Please save important work first.\n")

user_accept = ''

while(user_accept not in ['y', 'n']):
    user_accept = input("Are you ready?\n(y)es\n(n)o\n\n")

if user_accept == 'n':
    print("Take your time!")
    exit(1)

# ask for project directory, if necessary
while project_dir == '':
    project_dir = input(
        "Enter the full path of the repo's directory.\ne.g. ~/git/max-admin\n\n")

print("Checking out `master`...")
os.system("git checkout master; git pull")

if os.path.isfile(f"{project_dir}/package.json"):
    with open(f"{project_dir}/package.json", 'r') as f:
        package_contents = json.load(f)
        current_version = package_contents['version']

    release_type = ''
    current_version_split = current_version.split(".")

    while release_type not in ['h', 'p']:
        release_type = input(
            "\n\nIs this a (p)lanned release or a (h)otfix?\n\n")

    release_index = 1 if release_type == 'p' else 2

    current_version_split[release_index] = str(
        int(current_version_split[release_index]) + 1)

    new_version = ".".join(current_version_split)

    print(f"\n\nCool, let's bump to {new_version}.\n")

    new_branch = ''
    while(new_branch == ''):
        new_branch = input("What is your ticket number? Example: MAX-1234\n")

    print("\nChecking out new branch...")
    os.system(f"git checkout -b feature/{new_branch}")

    print("\n\nModifying package.json, package-lock.json...\n")

    # modify package, package-lock
    package_contents['version'] = new_version
    with open(f"{project_dir}/package.json", 'w') as f:
        json.dump(package_contents, f, indent=2)

    with open(f"{project_dir}/package-lock.json", 'r') as f:
        package_lock_contents = json.load(f)
        package_lock_contents['version'] = new_version

    with open(f"{project_dir}/package-lock.json", 'w') as f:
        json.dump(package_lock_contents, f, indent=2)

    print("\nPreparing pull request...\n\n")

    # commit modified files
    os.system(
        f"git add package.json; git add package-lock.json; git commit -m '{new_branch}: Bumped version to {new_version}'")

    # push
    print("\n\nPushing...\n\n")
    os.system(f"git push -u origin feature/{new_branch}")
else:
    print(f"Could not find {project_dir}/package.json")
