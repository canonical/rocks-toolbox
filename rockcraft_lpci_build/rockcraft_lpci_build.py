#!/usr/bin/python3

import argparse
import atexit
import base64
import distro_info
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

import yaml
from git import Repo

# Launchpad API docs: https://launchpad.net/+apidoc/devel.html
from launchpadlib.launchpad import Launchpad
from lazr.restfulclient.resource import Entry

# lpci reference: https://lpci.readthedocs.io/en/latest/configuration.html
LPCI_CONFIG_TEMPLATE = """
pipeline:
- build-rock

jobs:
  build-rock:
    # The "series" field is included by the code 
    # The "architectures" field is included by the code
    snaps:
    #   - name: lxd
      - name: chisel
        channel: latest/candidate
      - name: rockcraft
        classic: true
    run: |
        # lxd waitready
        # lxd init --auto
        # snap set lxd daemon.group=adm
        # snap restart lxd
        HTTPS_PROXY=${https_proxy} HTTP_PROXY=${http_proxy} rockcraft pack \
                --verbosity=trace --destructive-mode
    output:
      paths:
        - "*.rock"
"""


class LaunchpadBuildTimeout(Exception):
    pass


class LaunchpadBuildFailure(Exception):
    pass


class RockcraftLpciBuilds:
    def __init__(self) -> None:
        logging.basicConfig(level=logging.INFO)

        self.args = self.cli_args().parse_args()
        self.set_lp_creds()
        self.app_name = "rockcraft-lpci"
        self.rockcraft_yaml = Path("rockcraft.yaml")
        self.rockcraft_yaml_raw = self.read_rockcraft_yaml()
        try:
            self.rock_name = self.rockcraft_yaml_raw["name"]
        except KeyError:
            logging.exception(f"{self.rockcraft_yaml} is missing the 'name' field")
            raise
        self.launchpad = self.lp_login("production")
        self.lp_user = self.launchpad.me.name
        self.lp_owner = f"/~{self.lp_user}"
        self.lp_repo_name = f"{self.app_name}-{self.rock_name}-{int(time.time())}"
        self.lp_repo_path = f"~{self.lp_user}/+git/{self.lp_repo_name}"

    @staticmethod
    def cli_args() -> argparse.ArgumentParser:
        """Arguments parser"""
        parser = argparse.ArgumentParser(
            description="Builds rocks in Launchpad, with lpci.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        lp_creds = parser.add_mutually_exclusive_group(required=True)
        # E.g. if the LP credential file looks like:
        #       [1]
        #       consumer_key = System-wide: Debian GNU/Linux (9df369915b99)
        #       consumer_secret =
        #       access_token = foo
        #       access_secret = bar
        # then this arg's value should be `cat <file> | base64 -w 0`
        lp_creds.add_argument(
            "--lp-credentials-b64",
            help="raw, single-line and base64 enconded Launchpad credentials",
        )
        lp_creds.add_argument(
            "--lp-credentials-file",
            help=str(
                "the path to an existing Launchpad credentials file."
                "If passed, --lp-credentials-b64 is ignored"
            ),
        )
        parser.add_argument(
            "--timeout",
            default=3600,
            type=int,
            help=str(
                "time (in sec) after which to stop waiting for the build to finish"
            ),
        )
        parser.add_argument(
            "--allow-build-failures",
            action="store_true",
            help=str("acknowledge that uploaded project will be publicly available"),
        )
        parser.add_argument(
            "--launchpad-accept-public-upload",
            action="store_true",
            help=str("for multi-arch builds, continue even if some builds fail"),
        )

        return parser

    @staticmethod
    def delete_file(file_path: str) -> None:
        """Delete file"""
        try:
            os.remove(file_path)
            logging.info(f"File {file_path} deleted successfully.")
        except OSError as e:
            logging.exception(f"Error deleting file {file_path}: {e}")

    @staticmethod
    def lp_login_failure() -> None:
        """Callback function for when the Launchpad login fails"""
        logging.error("Unable to login to Launchpad with the provided credentials")
        sys.exit(1)

    @staticmethod
    def delete_git_repository(lp_client: Launchpad, lp_repo_path: str) -> None:
        git_repo = lp_client.git_repositories.getByPath(path=lp_repo_path)  # type: ignore

        if git_repo is None:
            return

        logging.info(f"Deleting repository {lp_repo_path} from Launchpad...")
        git_repo.lp_delete()

    @staticmethod
    def save_build_logs(lp_build: Entry) -> dict:
        ci_build = requests.get(lp_build.ci_build_link)
        ci_build.raise_for_status()
        ci_build = ci_build.json()

        if "build_log_url" in ci_build and ci_build["build_log_url"]:
            ci_build_logs = requests.get(ci_build["build_log_url"])
            with tempfile.NamedTemporaryFile(delete=False) as log:
                logging.info(f"Build log save at {log.name}")
                log.write(ci_build_logs.text.encode())

        else:
            logging.warning(
                f"Unable to get logs. build_log_url not in {lp_build.ci_build_link}."
            )

        return ci_build

    def ack_project_will_be_public(self) -> None:
        if self.args.launchpad_accept_public_upload:
            return

        print(
            "Your current directory will be sent to Launchpad and will be public!\n"
            "Are you sure you want to continue? [press y to continue]: "
        )
        key = input()
        if key != "y":
            sys.exit(0)

    def read_rockcraft_yaml(self) -> dict:
        self.check_rockcraft_yaml()
        with open(self.rockcraft_yaml) as rockfile:
            try:
                return yaml.safe_load(rockfile)
            except yaml.scanner.ScannerError:
                logging.exception(f"{self.rockcraft_yaml} cannot be read")
                raise

    def set_lp_creds(self) -> None:
        if self.args.lp_credentials_file:
            self.lp_creds = self.args.lp_credentials_file
            logging.info(f"Using file '{self.lp_creds}' for Launchpad authentication")
        else:
            fd, self.lp_creds = tempfile.mkstemp()
            atexit.register(self.delete_file, self.lp_creds)

            with os.fdopen(fd, "w") as tmp_lp_creds:
                tmp_lp_creds.write(
                    base64.b64decode(self.args.lp_credentials_b64).decode()
                )

            logging.info(f"Saved Launchpad credentials in {self.lp_creds}")

    def lp_login(self, lp_server: str) -> Launchpad:
        """Login to Launchpad"""
        return Launchpad.login_with(
            f"{self.rock_name} remote-build",
            lp_server,
            credentials_file=self.lp_creds,
            credential_save_failed=self.lp_login_failure,
            version="devel",
        )

    def check_rockcraft_yaml(self) -> None:
        if not self.rockcraft_yaml.exists():
            raise FileNotFoundError(f"File {self.rockcraft_yaml} not found")

    def create_git_repository(self) -> Entry:
        """Create git repository in LP"""
        logging.info(
            "Creating git repo: name=%s, owner=%s, target=%s",
            self.lp_repo_name,
            self.lp_owner,
            self.lp_owner,
        )
        return self.launchpad.git_repositories.new(
            name=self.lp_repo_name, owner=self.lp_owner, target=self.lp_owner
        )

    def prepare_local_project(self) -> None:
        self.lp_local_repo_path = tempfile.mkdtemp()
        project_path = os.getcwd()
        logging.info(
            f"Copying project from {project_path} to {self.lp_local_repo_path}"
        )
        shutil.copytree(project_path, self.lp_local_repo_path, dirs_exist_ok=True)

        logging.info(f"Initializing a new Git repo at {self.lp_local_repo_path}")
        if Path(f"{self.lp_local_repo_path}/.git").exists():
            shutil.rmtree(f"{self.lp_local_repo_path}/.git")

        # Just making sure we don't push the lp credentials
        if Path(
            f"{self.lp_local_repo_path}/{os.path.basename(self.lp_creds)}"
        ).exists():
            os.remove(f"{self.lp_local_repo_path}/{os.path.basename(self.lp_creds)}")

        self.lp_local_repo = Repo.init(self.lp_local_repo_path)

    def get_rock_archs(self) -> list:
        try:
            platforms = self.rockcraft_yaml_raw["platforms"]
        except KeyError:
            logging.exception(f"{self.rockcraft_yaml} is missing the platforms")
            raise

        archs = []
        for platf, values in platforms.items():
            if isinstance(values, dict) and "build-for" in values:
                archs.append(values["build-for"])
                continue

            archs.append(platf)

        return list(set(archs))

    def get_rock_build_base(self) -> str:
        try:
            build_base = self.rockcraft_yaml_raw["build_base"]
        except KeyError:
            try:
                build_base = self.rockcraft_yaml_raw["base"]
            except KeyError:
                logging.exception(f"{self.rockcraft_yaml} is missing the 'base' field")
                raise

        if build_base == "devel":
            return distro_info.UbuntuDistroInfo().devel()

        all_releases, all_codenames = (
            distro_info.UbuntuDistroInfo().get_all(result="fullname"),
            distro_info.UbuntuDistroInfo().get_all(),
        )

        build_base_release = build_base.replace(":", "@").split("@")[-1]
        build_base_full_release = list(
            filter(lambda r: build_base_release in r, all_releases)
        )[0]

        return all_codenames[all_releases.index(build_base_full_release)]

    def write_lpci_configuration_file(self) -> None:
        lpci_config = yaml.safe_load(LPCI_CONFIG_TEMPLATE)
        archs = self.get_rock_archs()
        build_base = self.get_rock_build_base()

        logging.info(
            f" !! This rock ({self.rock_name}) is being built on "
            f"{build_base}, for: {archs} !!"
        )
        self.target_build_count = len(archs)
        lpci_config["jobs"]["build-rock"]["architectures"] = archs
        lpci_config["jobs"]["build-rock"]["series"] = build_base
        lpci_config_file = f"{self.lp_local_repo_path}/.launchpad.yaml"
        logging.info(f"LPCI configuration file saved in {lpci_config_file}")

        with open(f"{self.lp_local_repo_path}/.launchpad.yaml", "w") as lpci_file:
            yaml.dump(lpci_config, lpci_file)

    def get_lp_token(self) -> str:
        # Add an extra 5min to the token just to make sure this script exits
        # before the token expires.
        date_expires = datetime.now(timezone.utc) + timedelta(
            seconds=self.args.timeout + 300
        )
        logging.info(
            f"Creating new Launchpad token for {self.lp_repo_name}. "
            f"It will expire on {date_expires.strftime('%Y-%m-%dT%H:%M:%S %Z')}"
        )
        return self.lp_repo.issueAccessToken(  # type: ignore
            description=f"rockcraft remote-build for {self.rock_name}",
            scopes=["repository:push"],
            date_expires=date_expires.isoformat(),
        )

    def push_to_lp(self, repo_url: str) -> None:
        self.lp_local_repo.git.add(A=True)
        self.lp_local_repo.index.commit(f"Initial commit: build {self.rock_name}")

        # Create a new branch
        branch_name = "master"
        # self.lp_local_repo.git.branch(branch_name)
        self.lp_local_repo.git.checkout(branch_name)

        logging.info(
            f"Pushing local project {self.lp_local_repo_path} "
            f"to {self.lp_repo.git_https_url}"
        )
        origin = self.lp_local_repo.create_remote("origin", url=repo_url)
        origin.push(f"{branch_name}:{branch_name}")

    def wait_for_lp_builds(self) -> list:
        logging.info(
            f"Waiting for builds to finish at {self.lp_repo_path}, "
            f"on branch {self.lp_local_repo.active_branch.name}"
        )

        keep_waiting = True
        wait_until = datetime.now() + timedelta(seconds=self.args.timeout)
        finished_builds = []
        successful_builds = []
        while keep_waiting:
            if wait_until < datetime.now():
                logging.error("Timed out. Keeping the Launchpad repo alive")
                atexit.unregister(self.delete_git_repository)
                raise LaunchpadBuildTimeout

            build_status = self.lp_repo.getStatusReports(
                commit_sha1=self.lp_local_repo.head.commit.hexsha
            )
            if len(build_status) != self.target_build_count:
                logging.warning(
                    f"Need {self.target_build_count} builds "
                    f"but Launchpad only listed {len(build_status)} so far. Waiting"
                )
                time.sleep(5)
                continue

            for build in build_status:
                if build.ci_build_link in finished_builds:
                    logging.debug(f"{build.ci_build_link} has finished already")
                    continue

                logging.debug(f"Tracking build at {build.ci_build_link}")
                if build.result in ["Failed", "Skipped", "Cancelled", "Succeeded"]:
                    finished_builds.append(build.ci_build_link)
                    ci_build = self.save_build_logs(build)
                    log_msg_prefix = f"[{ci_build.get('arch_tag', 'unknown arch')}]"
                    if build.result == "Succeeded":
                        logging.info(f"{log_msg_prefix} Build successful!")
                        successful_builds.append(build)
                        continue

                    # If it gets here, it means it is finished and not successful
                    error_msg = f"{log_msg_prefix} Build failed!"
                    if self.args.allow_build_failures:
                        logging.error(f"{error_msg}. Continuing")
                        continue
                    else:
                        logging.error(f"{error_msg}. Keeping the Launchpad repo alive")
                        atexit.unregister(self.delete_git_repository)
                        raise LaunchpadBuildFailure()

                # If we got here, it means the build is still in progress
                # We'll keep going until len(finished_builds) >= len(build_status)
            if len(finished_builds) >= len(build_status):
                logging.info("All builds have finished")
                break

            logging.info(
                f"{len(finished_builds)}/{len(build_status)} builds finished, waiting"
            )
            time.sleep(30)

        return successful_builds

    def download_build_artefacts(successful_builds: list) -> None:
        for build in successful_builds:
            artefact_urls = build.getArtifactURLs()
            rock_url = list(filter(lambda u: ".rock" in u, artefact_urls))
            if not rock_url:
                arch = build.distro_arch_series_link.split("/")[-1]
                logging.warning(
                    f"No rock artefacts found for {arch} (job {build.title})"
                )
                continue
            for url in rock_url:
                r = requests.get(url)
                r.raise_for_status()

                out_file = url.split("/")[-1]
                with open(out_file, "wb") as oci_archive:
                    oci_archive.write(r.content)

                logging.info(f"Downloaded {out_file} into current directory")

    def run(self) -> None:
        """Main function"""
        self.ack_project_will_be_public()
        logging.info(f"[launchpad] Logged in as {self.lp_user} ({self.launchpad.me})")
        self.prepare_local_project()

        logging.info(f"Creating .launchpad.yaml file...")
        self.write_lpci_configuration_file()
        self.lp_repo = self.create_git_repository()
        atexit.register(self.delete_git_repository, self.launchpad, self.lp_repo_path)
        token = self.get_lp_token()
        lp_repo_url = (
            f"https://{self.lp_user}:{token}@git.launchpad.net/"
            f"~{self.lp_user}/+git/{self.lp_repo_name}/"
        )
        logging.info(
            f"The remote for {self.lp_repo_name} is {lp_repo_url.replace(token, '***')}"
        )
        try:
            self.push_to_lp(lp_repo_url)
        except:
            logging.exception("Failed to push local project to Launchpad")
            # Graceful termination to allow for the cleanup
            return

        logging.info(
            " !! You can follow your builds at "
            f"{self.lp_repo.web_link}/+ref/{self.lp_local_repo.active_branch.name} !!"
        )

        successful_builds = self.wait_for_lp_builds()

        if not successful_builds:
            logging.error(f"No builds were successful! There are no rocks to retrieve")
            return

        self.download_build_artefacts(successful_builds)


if __name__ == "__main__":
    builder = RockcraftLpciBuilds()
    builder.run()
