"""End-to-end vault lifecycle against an isolated ephemeral wallet."""
from driver import actions


def test_create_vault_appears_in_drawer(ephemeral_wallet):
    client = ephemeral_wallet.client

    # Create a vault — it auto-opens into the identifiers page.
    page = actions.create_vault(client, "itvault", "secretpass")
    assert page.get("ok") is True
    assert page.get("vault_page")  # a vault sub-page is now active

    # The vault appears in the drawer's list.
    items = client.call("get_list_items", target="vaultDrawer.vaultList")
    assert any("itvault" in str(t) for t in items.get("items", []))


def test_close_then_reopen_vault(ephemeral_wallet):
    client = ephemeral_wallet.client

    # Create + auto-open, then close back to home.
    actions.create_vault(client, "reopenvault", "secretpass")
    actions.close_vault(client, "reopenvault")

    # Reopen with the same passcode — exercises the open-vault unlock flow.
    page = actions.open_vault(client, "reopenvault", "secretpass")
    assert page.get("ok") is True
    assert page.get("vault_page")  # a vault sub-page is active again
