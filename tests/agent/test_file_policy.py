"""Tests for FileAccessPolicy."""

import pytest
from mdpilot.agent.file_policy import FileAccessPolicy


@pytest.fixture
def policy():
    return FileAccessPolicy(node_id="lab03")


# --- can_read ---
def test_read_normal_file_allowed(policy):
    assert policy.can_read("/home/3-FF/changshengjie/output.pdb") is True


def test_read_arbitrary_file_allowed(policy):
    assert policy.can_read("/tmp/some_file.txt") is True


def test_read_env_file_blocked(policy):
    assert policy.can_read("/home/zhao/.env") is False


def test_read_ssh_key_blocked(policy):
    assert policy.can_read("/home/zhao/.ssh/id_rsa") is False


def test_read_ssh_dir_blocked(policy):
    assert policy.can_read("/root/.ssh/authorized_keys") is False


def test_read_pem_file_blocked(policy):
    assert policy.can_read("/home/zhao/cert.pem") is False


def test_read_key_file_blocked(policy):
    assert policy.can_read("/home/zhao/secret.key") is False


def test_read_token_file_blocked(policy):
    assert policy.can_read("/home/zhao/api.token") is False


def test_read_etc_shadow_blocked(policy):
    assert policy.can_read("/etc/shadow") is False


def test_read_etc_passwd_blocked(policy):
    assert policy.can_read("/etc/passwd") is False


# --- can_write ---

def test_write_inside_changshengjie_allowed(policy):
    assert policy.can_write("/home/3-FF/changshengjie/run/output.nc") is True


def test_write_changshengjie_root_allowed(policy):
    assert policy.can_write("/home/3-FF/changshengjie/file.txt") is True


def test_write_outside_changshengjie_blocked(policy):
    assert policy.can_write("/home/3-FF/other/file.txt") is False


def test_write_home_dir_blocked(policy):
    assert policy.can_write("/home/zhao/file.txt") is False


def test_write_tmp_blocked(policy):
    assert policy.can_write("/tmp/file.txt") is False


def test_write_path_traversal_blocked(policy):
    # Resolves to /etc/passwd — must be blocked
    assert policy.can_write("/home/3-FF/changshengjie/../../etc/passwd") is False


def test_write_path_traversal_sibling_blocked(policy):
    assert policy.can_write("/home/3-FF/changshengjie/../other/file.txt") is False


# --- can_execute ---

def test_execute_inside_changshengjie_allowed(policy):
    assert policy.can_execute("/home/3-FF/changshengjie/run.sh") is True


def test_execute_outside_changshengjie_blocked(policy):
    assert policy.can_execute("/usr/bin/python3") is False


def test_execute_path_traversal_blocked(policy):
    assert policy.can_execute("/home/3-FF/changshengjie/../../bin/bash") is False


# --- unknown node ---

def test_unknown_node_raises():
    with pytest.raises(KeyError):
        FileAccessPolicy(node_id="lab99")


# --- cross-node isolation ---

def test_write_wrong_node_changshengjie_blocked():
    policy_lab02 = FileAccessPolicy(node_id="lab02")
    # lab03's changshengjie is not writable from lab02's policy
    assert policy_lab02.can_write("/home/3-FF/changshengjie/file.txt") is False


def test_write_correct_node_changshengjie_allowed():
    policy_lab02 = FileAccessPolicy(node_id="lab02")
    assert policy_lab02.can_write("/home/2-BB/changshengjie/file.txt") is True
