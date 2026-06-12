from driver import actions


class FakeClient:
    """Records calls and returns canned replies — no socket, no wallet."""

    def __init__(self, responses=None):
        self.calls: list = []
        self._responses = responses or {}

    def call(self, op, **kwargs):
        self.calls.append((op, kwargs))
        return self._responses.get(op, {"ok": True})

    def wait_for(self, target, condition="visible", timeout_ms=5000, occurrence=0):
        self.calls.append(("wait_for", {"target": target, "condition": condition}))
        return {"ok": True}


def test_create_vault_issues_expected_sequence():
    fake = FakeClient(responses={"current_page": {"ok": True, "vault_page": "identifiers"}})

    result = actions.create_vault(fake, "automation", "noble")

    ops = [c[0] for c in fake.calls]
    assert ops == [
        "click", "click_list_item", "wait_for", "type", "type",
        "click", "wait_for", "current_page",
    ]
    assert ("type", {"target": "createVaultDialog.nameField", "text": "automation"}) in fake.calls
    assert ("type", {"target": "createVaultDialog.passcodeField", "text": "noble"}) in fake.calls
    assert result == {"ok": True, "vault_page": "identifiers"}


def test_open_vault_targets_named_vault_then_types_passcode():
    fake = FakeClient(responses={"current_page": {"ok": True, "vault_page": "identifiers"}})

    actions.open_vault(fake, "automation", "noble")

    assert ("click", {"target": "vaultDrawer.open.automation"}) in fake.calls
    assert ("type", {"target": "openVaultDialog.passcodeField", "text": "noble"}) in fake.calls
    assert ("click", {"target": "openVaultDialog.openButton"}) in fake.calls


def test_open_designer_clicks_nav_and_returns_page():
    fake = FakeClient(responses={"current_page": {"ok": True, "vault_page": "designer.overview"}})

    result = actions.open_designer(fake)

    assert ("click", {"target": "designer.navButton"}) in fake.calls
    assert result == {"ok": True, "vault_page": "designer.overview"}
