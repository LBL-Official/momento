"""Persistent member_id. Position is order only."""

from __future__ import annotations

import pytest

from roller.stax.membership import add_member, definition_hash, remove_member, reorder_members
from roller.stax.models import ConstraintViolation
from tests.stax_fixtures import source


def test_add_remove_reorder_preserves_member_id():
    members = add_member([], source(name="A", question_hash="a"), stax_id="STAX-0001", member_seq=1)
    members = add_member(members, source(name="B", question_hash="b"), stax_id="STAX-0001", member_seq=2)
    members = add_member(members, source(name="C", question_hash="c"), stax_id="STAX-0001", member_seq=3)
    assert [m["member_id"] for m in members] == ["STXM-0001", "STXM-0002", "STXM-0003"]
    assert members[0]["display_id"] == "STX01-S01"
    first = members[0]["member_id"]
    roller = members[0]["roller_object_id"]
    members = reorder_members(members, ["STXM-0003", "STXM-0001", "STXM-0002"], stax_id="STAX-0001")
    by_id = {m["member_id"]: m for m in members}
    assert by_id[first]["position"] == 2
    assert by_id[first]["roller_object_id"] == roller
    assert by_id[first]["display_id"] == "STX01-S02"
    members = remove_member(members, "STXM-0002", stax_id="STAX-0001")
    assert [m["member_id"] for m in members] == ["STXM-0003", "STXM-0001"]
    assert members[0]["position"] == 1


def test_incompatible_add_rejected():
    members = add_member([], source(leagues=("NBA",)), stax_id="STAX-0001", member_seq=1)
    with pytest.raises(ConstraintViolation):
        add_member(members, source(leagues=("NCAAB",)), stax_id="STAX-0001", member_seq=2)


def test_reorder_changes_definition_hash():
    members = add_member([], source(name="A", question_hash="a"), stax_id="STAX-0001", member_seq=1)
    members = add_member(members, source(name="B", question_hash="b"), stax_id="STAX-0001", member_seq=2)
    before = definition_hash(members)
    reordered = reorder_members(members, ["STXM-0002", "STXM-0001"], stax_id="STAX-0001")
    assert definition_hash(reordered) != before
    assert members[0]["member_id"] == reordered[1]["member_id"]
