#!/usr/bin/python3

"""Takes a rockcraft.yaml file from the current directory and offloads the
corresponding builds to Launchpad, via lpci."""

import argparse
import atexit
import base64
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast
import distro_info
import requests
import yaml
from git import Repo

# Launchpad API docs: https://launchpad.net/+apidoc/devel.html
from launchpadlib.launchpad import Launchpad
from lazr.restfulclient.resource import Entry
from retry import retry

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
    """Custom exception for LP timeouts"""


class LaunchpadBuildFailure(Exception):
    """Custom exception for LP build failures"""


class LaunchpadBuildMissingRockArtefacts(Exception):
    """Custom exception for LP builds that miss their artefacts"""


class RockcraftLpciBuilds:
    """The LPCI build class"""

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
            logging.exception("%s is missing the 'name' field", self.rockcraft_yaml)
            raise
        self.launchpad = self.lp_login("production")
        self.lp_user = self.launchpad.me.name
        self.lp_owner = f"/~{self.lp_user}"
        self.lp_repo_name = f"{self.app_name}-{self.rock_name}-{int(time.time())}"
        self.lp_repo_path = f"~{self.lp_user}/+git/{self.lp_repo_name}"
        # The following are defined during the script execution
        self.lp_repo = self.lp_local_repo = self.lp_local_repo_path = None
        self.target_build_count = 0

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
            logging.info("File %s deleted successfully.", file_path)
        except OSError as err:
            logging.exception("Error deleting file %s: %s", file_path, err)

    @staticmethod
    def lp_login_failure() -> None:
        """Callback function for when the Launchpad login fails"""
        logging.error("Unable to login to Launchpad with the provided credentials")
        sys.exit(1)

    @staticmethod
    def delete_git_repository(lp_client: Launchpad, lp_repo_path: str) -> None:
        """Delete a git repo from Launchpad"""
        git_repo = lp_client.git_repositories.getByPath(path=lp_repo_path)  # type: ignore

        if git_repo is None:
            return

        logging.info("Deleting repository %s from Launchpad...", lp_repo_path)
        git_repo.lp_delete()

    @staticmethod
    def save_build_logs(ci_build: Entry) -> None:
        """Fetch build logs from Launchpad and save them locally"""
        if ci_build.build_log_url:
            ci_build_logs = requests.get(ci_build.build_log_url)
            with tempfile.NamedTemporaryFile(delete=False) as log:
                logging.info("Build log save at %s", log.name)
                log.write(ci_build_logs.text.encode())

        else:
            logging.warning(
                "Unable to get logs. build_log_url not in %s.", ci_build.web_link
            )

    @staticmethod
    @retry(LaunchpadBuildMissingRockArtefacts, tries=3, delay=30, backoff=2)
    def get_artefact_urls(build: Entry) -> list:
        """List the build artefacts, retrying if they are not immediately available"""
        arch = build.distro_arch_series_link.split("/")[-1]

        artefact_urls = build.getArtifactURLs()
        rock_urls = list(filter(lambda u: ".rock" in u, artefact_urls))
        logging.info("List of artefacts for %s: %s", arch, artefact_urls)
        if not rock_urls:
            raise LaunchpadBuildMissingRockArtefacts(
                f"No rock artefacts found for {arch} (job {build.title})"
            )

        return rock_urls

    def download_build_artefacts(self, successful_builds: list) -> None:
        """Download rocks from the successful LP builds"""
        for build in successful_builds:
            rock_urls = self.get_artefact_urls(build)
            for url in rock_urls:
                download = requests.get(url)
                download.raise_for_status()

                out_file = url.split("/")[-1]
                with open(out_file, "wb") as oci_archive:
                    oci_archive.write(download.content)

                logging.info("Downloaded %s into current directory", out_file)

    def ack_project_will_be_public(self) -> None:
        """Ask for the consent about the project becoming public in Launchpad"""
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
        """Parse the rockcraft.yaml file"""
        self.check_rockcraft_yaml()
        with open(self.rockcraft_yaml, "r", encoding="utf-8") as rockfile:
            try:
                return yaml.safe_load(rockfile)
            except yaml.scanner.ScannerError:
                logging.exception("%s cannot be read", self.rockcraft_yaml)
                raise

    def set_lp_creds(self) -> None:
        """Set the LP credentials file locally"""
        if self.args.lp_credentials_file:
            self.lp_creds = self.args.lp_credentials_file
            logging.info("Using file '%s' for Launchpad authentication", self.lp_creds)
        else:
            file_d, self.lp_creds = tempfile.mkstemp()
            atexit.register(self.delete_file, self.lp_creds)

            with os.fdopen(file_d, "w") as tmp_lp_creds:
                tmp_lp_creds.write(
                    base64.b64decode(self.args.lp_credentials_b64).decode()
                )

            logging.info("Saved Launchpad credentials in %s", self.lp_creds)

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
        """Make sure the rockcraft.yaml file exists"""
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
        """Initiate a local Git repo for the project"""
        self.lp_local_repo_path = tempfile.mkdtemp()
        project_path = os.getcwd()
        logging.info(
            "Copying project from %s to %s", project_path, self.lp_local_repo_path
        )
        shutil.copytree(project_path, self.lp_local_repo_path, dirs_exist_ok=True)

        logging.info("Initializing a new Git repo at %s", self.lp_local_repo_path)
        if Path(f"{self.lp_local_repo_path}/.git").exists():
            shutil.rmtree(f"{self.lp_local_repo_path}/.git")

        # Just making sure we don't push the lp credentials
        if Path(
            f"{self.lp_local_repo_path}/{os.path.basename(self.lp_creds)}"
        ).exists():
            os.remove(f"{self.lp_local_repo_path}/{os.path.basename(self.lp_creds)}")

        self.lp_local_repo = Repo.init(self.lp_local_repo_path)

    def get_rock_archs(self) -> list:
        """Infer archs from rockcraft.yaml's platforms"""
        try:
            platforms = self.rockcraft_yaml_raw["platforms"]
        except KeyError:
            logging.exception("%s is missing the platforms", self.rockcraft_yaml)
            raise

        archs = []
        for platf, values in platforms.items():
            if isinstance(values, dict) and "build-for" in values:
                archs.append(values["build-for"])
                continue

            archs.append(platf)

        return list(set(archs))

    def get_rock_build_base(self) -> str:
        """Infer the Ubuntu series for lpci, from the rockcraft.yaml file"""
        try:
            build_base = self.rockcraft_yaml_raw["build_base"]
        except KeyError:
            try:
                build_base = self.rockcraft_yaml_raw["base"]
            except KeyError:
                logging.exception("%s is missing the 'base' field", self.rockcraft_yaml)
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
        """Write the .launchpad.yaml file"""
        lpci_config = yaml.safe_load(LPCI_CONFIG_TEMPLATE)
        archs = self.get_rock_archs()
        build_base = self.get_rock_build_base()

        logging.info(
            " !! This rock (%s) is being built on %s, for: %s !!",
            self.rock_name,
            build_base,
            archs,
        )
        self.target_build_count = len(archs)
        lpci_config["jobs"]["build-rock"]["architectures"] = archs
        lpci_config["jobs"]["build-rock"]["series"] = build_base
        lpci_config_file = f"{self.lp_local_repo_path}/.launchpad.yaml"
        logging.info("LPCI configuration file saved in %s", lpci_config_file)

        with open(
            f"{self.lp_local_repo_path}/.launchpad.yaml", "w", encoding="utf-8"
        ) as lpci_file:
            yaml.dump(lpci_config, lpci_file)

    def get_lp_token(self) -> str:
        """Get an LP token for the Git remote URL"""
        # Add an extra 5min to the token just to make sure this script exits
        # before the token expires.
        date_expires = datetime.now(timezone.utc) + timedelta(
            seconds=self.args.timeout + 300
        )
        logging.info(
            "Creating new Launchpad token for %s. It will expire on %s",
            self.lp_repo_name,
            date_expires.strftime("%Y-%m-%dT%H:%M:%S %Z"),
        )
        return self.lp_repo.issueAccessToken(  # type: ignore
            description=f"rockcraft remote-build for {self.rock_name}",
            scopes=["repository:push"],
            date_expires=date_expires.isoformat(),
        )

    def push_to_lp(self, repo_url: str) -> None:
        """Push local git repo to LP"""
        self.lp_local_repo.git.add(A=True)
        self.lp_local_repo.index.commit(f"Initial commit: build {self.rock_name}")

        # Create a new branch
        branch_name = "master"
        # self.lp_local_repo.git.branch(branch_name)
        self.lp_local_repo.git.checkout(branch_name)

        logging.info(
            "Pushing local project %s to %s",
            self.lp_local_repo_path,
            self.lp_repo.git_https_url,
        )
        origin = self.lp_local_repo.create_remote("origin", url=repo_url)
        origin.push(f"{branch_name}:{branch_name}")

    def wait_for_lp_builds(self) -> list:
        """Wait for all LP builds to finish"""
        logging.info(
            "Waiting for builds to finish at %s, on branch %s",
            self.lp_repo_path,
            self.lp_local_repo.active_branch.name,
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
                    "Need %s builds but Launchpad only listed %s so far. Waiting",
                    self.target_build_count,
                    len(build_status),
                )
                time.sleep(5)
                continue

            for build in build_status:
                if build.ci_build_link in finished_builds:
                    logging.debug("%s has finished already", build.ci_build_link)
                    continue

                ci_build = self.launchpad.load(build.ci_build_link)
                log_msg_prefix = f"[{ci_build.arch_tag}]"

                # See buildstates at https://launchpad.net/+apidoc/devel.html#ci_build
                if any(
                    sub_state in ci_build.buildstate.lower()
                    for sub_state in ["failed", "problem", "cancelled", "successfully"]
                ):
                    finished_builds.append(build.ci_build_link)
                    self.save_build_logs(ci_build)
                    if "successfully" in ci_build.buildstate.lower():
                        logging.info("%s Build successful!", log_msg_prefix)
                        successful_builds.append(build)
                        continue

                    # If it gets here, it means it is finished and not successful
                    error_msg = f"{log_msg_prefix} Build failed!"
                    if self.args.allow_build_failures:
                        logging.error("%s Continuing", error_msg)
                        continue

                    logging.error("%s. Keeping the Launchpad repo alive", error_msg)
                    atexit.unregister(self.delete_git_repository)
                    raise LaunchpadBuildFailure()
                else:
                    logging.info("%s State: %s", log_msg_prefix, ci_build.buildstate)

                # If we got here, it means the build is still in progress
                # We'll keep going until len(finished_builds) >= len(build_status)
            if len(finished_builds) >= len(build_status):
                logging.info("All builds have finished")
                break

            logging.info(
                "%s builds finished, waiting",
                f"{len(finished_builds)}/{len(build_status)}",
            )
            time.sleep(30)

        return successful_builds

    def run(self) -> None:
        """Main function"""
        self.ack_project_will_be_public()
        logging.info(
            "[launchpad] Logged in as %s (%s)", self.lp_user, self.launchpad.me
        )
        self.prepare_local_project()

        logging.info("Creating .launchpad.yaml file...")
        self.write_lpci_configuration_file()
        self.lp_repo = self.create_git_repository()
        atexit.register(self.delete_git_repository, self.launchpad, self.lp_repo_path)
        token = self.get_lp_token()
        lp_repo_url = (
            f"https://{self.lp_user}:{token}@git.launchpad.net/"
            f"~{self.lp_user}/+git/{self.lp_repo_name}/"
        )
        logging.info(
            "The remote for %s is %s",
            self.lp_repo_name,
            lp_repo_url.replace(token, "***"),
        )
        try:
            self.push_to_lp(lp_repo_url)
        except Exception:  # pylint: disable=W0703
            # Catch anything, for a graceful termination, to allow for the cleanup
            logging.exception("Failed to push local project to Launchpad")
            return

        logging.info(
            " !! You can follow your builds at %s !!",
            f"{self.lp_repo.web_link}/+ref/{self.lp_local_repo.active_branch.name}",
        )

        successful_builds = self.wait_for_lp_builds()

        if not successful_builds:
            logging.error("No builds were successful! There are no rocks to retrieve")
            return

        self.download_build_artefacts(successful_builds)


if __name__ == "__main__":
    builder = RockcraftLpciBuilds()
    builder.run()
