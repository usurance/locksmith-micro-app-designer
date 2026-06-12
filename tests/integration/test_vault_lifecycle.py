"""End-to-end vault lifecycle against an isolated ephemeral wallet."""
from driver import actions


def test_create_then_reopen_vault(ephemeral_wallet):
    client = ephemeral_wallet.client

    # Create a vault — it auto-opens into the identifiers page.
    page = actions.create_vault(client, "itvault", "secretpass")
    assert page.get("ok") is True
    assert page.get("vault_page")  # a vault sub-page is now active

    # The vault appears in the drawer's list.
    items = client.call("get_list_items", target="vaultDrawer.vaultList")
    assert any("itvault" in str(t) for t in items.get("items", []))
