import argparse
import pathlib
import re
import sys
from unittest.mock import DEFAULT, MagicMock, call, mock_open, patch
import os
import pytest
import retry

from rockcraft_lpci_build import rockcraft_lpci_build


@pytest.fixture()
def mock_cli_args(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.cli_args"
    )


@pytest.fixture()
def mock_set_lp_creds(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.set_lp_creds"
    )


@pytest.fixture()
def mock_read_rockcraft_yaml(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.read_rockcraft_yaml"
    )


@pytest.fixture()
def mock_lp_login(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.lp_login"
    )


@pytest.fixture()
def mock_os_remove(mocker):
    return mocker.patch("os.remove")


@pytest.fixture()
def mock_lp_client(mocker):
    return mocker.patch("rockcraft_lpci_build.rockcraft_lpci_build.Launchpad")


@pytest.fixture()
def mock_ci_build(mocker):
    return mocker.patch("rockcraft_lpci_build.rockcraft_lpci_build.Entry")


@pytest.fixture()
def mock_requests(mocker):
    return mocker.patch("rockcraft_lpci_build.rockcraft_lpci_build.requests")


@pytest.fixture()
def mock_tempfile(mocker):
    return mocker.patch("rockcraft_lpci_build.rockcraft_lpci_build.tempfile")


@pytest.fixture()
def mock_get_artefact_urls(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.get_artefact_urls"
    )


@pytest.fixture()
def mock_builder(
    mock_cli_args, mock_set_lp_creds, mock_read_rockcraft_yaml, mock_lp_login
):
    return rockcraft_lpci_build.RockcraftLpciBuilds()


@pytest.fixture()
def mock_generic_builder(mocker):
    return MagicMock()


@pytest.fixture()
def mock_check_rockcraft_yaml(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.check_rockcraft_yaml"
    )


@pytest.fixture()
def mock_atexit(mocker):
    return mocker.patch("rockcraft_lpci_build.rockcraft_lpci_build.atexit")


@pytest.fixture()
def mock_repo(mocker):
    return mocker.patch("rockcraft_lpci_build.rockcraft_lpci_build.Repo")


@pytest.fixture()
def mock_get_rock_archs(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.get_rock_archs"
    )


@pytest.fixture()
def mock_get_rock_build_base(mocker):
    return mocker.patch(
        "rockcraft_lpci_build.rockcraft_lpci_build.RockcraftLpciBuilds.get_rock_build_base"
    )


class TestRockcraftLpciBuilds:
    def test_global_attributes(self):
        assert rockcraft_lpci_build.LPCI_CONFIG_TEMPLATE

    def test_attributes(
        self, mock_cli_args, mock_set_lp_creds, mock_read_rockcraft_yaml, mock_lp_login
    ):
        obj = rockcraft_lpci_build.RockcraftLpciBuilds()
        mock_cli_args.assert_called_once()
        mock_set_lp_creds.assert_called_once()
        assert obj.app_name == "rockcraft-lpci"
        assert obj.rockcraft_yaml == pathlib.Path("rockcraft.yaml")
        mock_read_rockcraft_yaml.assert_called_once()
        assert obj.rock_name
        mock_lp_login.assert_called_once_with("production")
        assert obj.lp_user
        assert obj.lp_owner
        assert obj.lp_repo_name
        assert obj.lp_repo_path
        assert obj.lp_repo == obj.lp_local_repo == obj.lp_local_repo_path == None
        assert obj.target_build_count == 0

    def test_cli_args_missing_args(self):
        with pytest.raises(SystemExit):
            obj = rockcraft_lpci_build.RockcraftLpciBuilds()
            obj.cli_args().parse_args()

    def test_delete_file(self, mock_os_remove):
        rockcraft_lpci_build.RockcraftLpciBuilds.delete_file("foo")
        mock_os_remove.assert_called_once_with("foo")

    def test_delete_git_repository(self, mock_lp_client):
        mock_lp_client.git_repositories.getByPath.return_value = MagicMock()
        rockcraft_lpci_build.RockcraftLpciBuilds.delete_git_repository(
            mock_lp_client, "foo"
        )
        mock_lp_client.git_repositories.getByPath.assert_called_once_with(path="foo")

    def test_save_build_logs(self, mock_ci_build, mock_requests, mock_tempfile):
        mock_ci_build.build_log_url = None
        rockcraft_lpci_build.RockcraftLpciBuilds.save_build_logs(mock_ci_build)
        mock_requests.assert_not_called()

        mock_ci_build.build_log_url = "foo"
        rockcraft_lpci_build.RockcraftLpciBuilds.save_build_logs(mock_ci_build)
        mock_requests.get.assert_called_once_with("foo")
        mock_tempfile.NamedTemporaryFile.assert_called_once_with(delete=False)

    def test_get_artefact_urls(self, mock_ci_build):
        mock_ci_build.distro_arch_series_link = "foo/bar"

        def dontretry(f, *args, **kw):
            return f()

        with pytest.raises(rockcraft_lpci_build.LaunchpadBuildMissingRockArtefacts):
            with patch.object(retry.api, "__retry_internal", dontretry):
                rockcraft_lpci_build.RockcraftLpciBuilds.get_artefact_urls(
                    mock_ci_build
                )
                mock_ci_build.getArtifactURLs.assert_called_once()

        mock_ci_build.getArtifactURLs.return_value = ["artifact.rock", "other"]
        with patch.object(retry.api, "__retry_internal", dontretry):
            out = rockcraft_lpci_build.RockcraftLpciBuilds.get_artefact_urls(
                mock_ci_build
            )
            assert out == ["artifact.rock"]

    def test_download_build_artefacts(
        self, mock_builder, mock_requests, mock_get_artefact_urls
    ):
        mock_builder.download_build_artefacts(successful_builds=[])
        mock_requests.assert_not_called()
        mock_get_artefact_urls.assert_not_called()

        mock_builder.download_build_artefacts(successful_builds=["foo"])
        mock_get_artefact_urls.assert_called_once_with("foo")

        mock_get_artefact_urls.return_value = ["url"]
        with patch("builtins.open", mock_open()) as m:
            mock_builder.download_build_artefacts(successful_builds=["foo"])
            mock_requests.get.assert_called_once_with("url")
            mock_requests.raise_for_status.aassert_called_once()
            m.assert_called_once_with("url", "wb")

    def test_ack_project_will_be_public(self, mock_builder):
        mock_builder.ack_project_will_be_public()

        with patch("builtins.input", lambda *args: "y"):
            mock_builder.args.launchpad_accept_public_upload = None
            mock_builder.ack_project_will_be_public()

        with patch("builtins.input", lambda *args: "n"):
            with patch("sys.exit") as sysexit:
                mock_builder.ack_project_will_be_public()
                sysexit.assert_called_once_with(0)

    def test_read_rockcraft_yaml(self):
        mock_obj = MagicMock()
        mock_obj.rockcraft_yaml = "foo"
        with patch("builtins.open", mock_open()) as m:
            with patch("yaml.safe_load") as yaml:
                rockcraft_lpci_build.RockcraftLpciBuilds.read_rockcraft_yaml(mock_obj)
                mock_obj.check_rockcraft_yaml.assert_called_once()
                m.assert_called_once_with("foo", "r", encoding="utf-8")
                yaml.assert_called_once()

    def test_set_lp_creds(self, mock_atexit):
        mock_obj = MagicMock()
        mock_obj.args.lp_credentials_file = 1
        rockcraft_lpci_build.RockcraftLpciBuilds.set_lp_creds(mock_obj)

        mock_obj.args.lp_credentials_file = 0
        mock_obj.args.lp_credentials_b64 = "foo"
        with patch("base64.b64decode") as base64:
            with patch("tempfile.mkstemp") as tempfile:
                tempfile.return_value = ("foo", "bar")
                with patch("os.fdopen", mock_open()) as m:
                    rockcraft_lpci_build.RockcraftLpciBuilds.set_lp_creds(mock_obj)
                    tempfile.assert_called_once()
                    mock_atexit.register.assert_called_once()
                    base64.assert_called_once_with("foo")

    def test_lp_login(self, mock_generic_builder):
        with patch("launchpadlib.launchpad.Launchpad.login_with") as login:
            mock_generic_builder.rock_name = "rock"
            mock_generic_builder.lp_creds = "creds"
            rockcraft_lpci_build.RockcraftLpciBuilds.lp_login(
                mock_generic_builder, "server"
            )
            login.assert_called_once_with(
                "rock remote-build",
                "server",
                credentials_file="creds",
                credential_save_failed=mock_generic_builder.lp_login_failure,
                version="devel",
            )

    def test_check_rockcraft_yaml(self, mock_builder):
        with pytest.raises(FileNotFoundError):
            mock_builder.check_rockcraft_yaml()

    def test_create_git_repository(self, mock_builder):
        mock_builder.create_git_repository()
        mock_builder.launchpad.git_repositories.new.assert_called_once()

    @patch("tempfile.mkdtemp")
    @patch("os.getcwd")
    @patch("os.remove")
    @patch("shutil.copytree")
    @patch("shutil.rmtree")
    def test_prepare_local_project(
        self,
        mock_rmtree,
        mock_copytree,
        mock_remove,
        mock_getcwd,
        mock_mkdtemp,
        mock_builder,
        mock_repo,
    ):
        mock_builder.lp_creds = "creds"
        mock_builder.prepare_local_project()
        mock_mkdtemp.assert_called_once()
        mock_getcwd.assert_called_once()
        mock_copytree.assert_called_once()
        mock_rmtree.assert_not_called()
        mock_remove.assert_not_called()
        mock_repo.init.assert_called_once()

    def test_get_rock_archs(self, mock_builder):
        mock_builder.rockcraft_yaml_raw = {}
        with pytest.raises(KeyError):
            mock_builder.get_rock_archs()

        mock_builder.rockcraft_yaml_raw = {"platforms": {"amd64": ""}}
        archs = mock_builder.get_rock_archs()
        assert archs == ["amd64"]

    @patch("distro_info.UbuntuDistroInfo.devel")
    @patch("distro_info.UbuntuDistroInfo.get_all")
    def test_get_rock_build_base(
        self, mock_distro_info_get_all, mock_distro_info_devel, mock_builder
    ):
        mock_builder.rockcraft_yaml_raw = {}
        with pytest.raises(KeyError):
            mock_builder.get_rock_build_base()

        mock_builder.rockcraft_yaml_raw = {"build_base": "devel"}
        mock_distro_info_devel.return_value = "dev"
        base = mock_builder.get_rock_build_base()
        assert base == "dev"

        mock_builder.rockcraft_yaml_raw = {"base": "ubuntu@22.04"}
        mock_distro_info_get_all.return_value = ["22.04", "24.04"]
        base = mock_builder.get_rock_build_base()
        assert base == "22.04"
        mock_distro_info_devel.assert_called_once()
        assert mock_distro_info_get_all.call_count == 2

    def test_write_lpci_configuration_file(
        self, mock_builder, mock_get_rock_archs, mock_get_rock_build_base
    ):
        with patch("yaml.safe_load") as yaml:
            with patch("builtins.open", mock_open()) as m:
                with patch("yaml.dump") as dump:
                    mock_builder.write_lpci_configuration_file()
                    yaml.assert_called_once_with(
                        rockcraft_lpci_build.LPCI_CONFIG_TEMPLATE
                    )
                    mock_get_rock_archs.assert_called_once()
                    mock_get_rock_build_base.assert_called_once()
                    m.assert_called_once_with(
                        f"{mock_builder.lp_local_repo_path}/.launchpad.yaml",
                        "w",
                        encoding="utf-8",
                    )
                    dump.assert_called_once()

    def test_get_lp_token(self, mock_builder):
        mock_builder.args.timeout = 0
        mock_builder.lp_repo = MagicMock()
        mock_builder.get_lp_token()
        mock_builder.lp_repo.issueAccessToken.assert_called_once()

    def test_push_to_lp(self, mock_builder):
        mock_builder.lp_local_repo = MagicMock()
        mock_builder.lp_repo = MagicMock()
        origin = MagicMock()
        mock_builder.lp_local_repo.create_remote.return_value = origin
        mock_builder.push_to_lp("url")
        mock_builder.lp_local_repo.git.add.assert_called_once_with(A=True)
        mock_builder.lp_local_repo.index.commit.assert_called_once()
        mock_builder.lp_local_repo.git.checkout.assert_called_once_with("master")
        mock_builder.lp_local_repo.create_remote.assert_called_once_with(
            "origin", url="url"
        )
        origin.push.assert_called_once()

    def test_wait_for_lp_builds(self, mock_builder, mock_atexit):
        # TODO: missing tests for multiple scenarios
        mock_builder.args.timeout = 1
        mock_builder.lp_local_repo = MagicMock()
        mock_builder.lp_repo = MagicMock()
        mock_builder.lp_repo.getStatusReports.return_value = []
        mock_builder.wait_for_lp_builds()
        mock_builder.lp_repo.getStatusReports.assert_called_once()
