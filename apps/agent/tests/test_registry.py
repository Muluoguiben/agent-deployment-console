import pytest

from agent_service import registry


def test_seed_version_is_live(conn):
    live = registry.get_live_version(conn)
    assert live.id == 1
    assert live.tools_enabled == registry.ALL_TOOLS


def test_deploy_and_rollback(conn):
    v2 = registry.create_version(
        conn, label="v2", system_prompt="p2", model="scripted:none"
    )
    registry.deploy(conn, v2)
    assert registry.get_live_version(conn).id == v2
    assert registry.previous_version_id(conn) == 1

    rolled = registry.rollback(conn)
    assert rolled == 1
    assert registry.get_live_version(conn).id == 1
    # rollback is symmetric: previous now points at v2
    assert registry.previous_version_id(conn) == v2


def test_deploy_unknown_version_fails(conn):
    with pytest.raises(ValueError):
        registry.deploy(conn, 999)


def test_list_versions_marks_live(conn):
    versions = registry.list_versions(conn)
    assert len(versions) == 1
    assert versions[0]["live"] is True
