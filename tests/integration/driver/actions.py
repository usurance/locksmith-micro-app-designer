"""Layer 2: reusable wallet actions composing Layer 0 (client) + Layer 1
(selectors). Each verb ends in a wait_for so the UI is settled on return, and
returns the resulting current_page for assertions. Works against any client
exposing call()/wait_for() — the live Client or a test fake.
"""
from __future__ import annotations

from driver import selectors as S


def create_vault(client, name: str, passcode: str) -> dict:
    """Open the drawer, fill the create dialog, submit; return current_page."""
    client.call("click", target=S.Toolbar.VAULTS_BUTTON)
    client.call("click_list_item", text=S.VaultDrawer.NEW_VAULT_ITEM)
    client.wait_for(S.CreateVaultDialog.NAME)
    client.call("type", target=S.CreateVaultDialog.NAME, text=name)
    client.call("type", target=S.CreateVaultDialog.PASSCODE, text=passcode)
    client.call("click", target=S.CreateVaultDialog.CREATE)
    client.wait_for(S.CreateVaultDialog.NAME, condition="hidden")
    return client.call("current_page")


def open_vault(client, name: str, passcode: str) -> dict:
    """Open the drawer, click the named vault's Open, unlock; return current_page."""
    client.call("click", target=S.Toolbar.VAULTS_BUTTON)
    client.call("click", target=S.VaultDrawer.open_button(name))
    client.wait_for(S.OpenVaultDialog.PASSCODE)
    client.call("type", target=S.OpenVaultDialog.PASSCODE, text=passcode)
    client.call("click", target=S.OpenVaultDialog.OPEN)
    client.wait_for(S.OpenVaultDialog.PASSCODE, condition="hidden")
    return client.call("current_page")


def open_designer(client) -> dict:
    """Click the designer plugin's nav entry; return the resulting current_page."""
    client.call("click", target=S.Designer.NAV_BUTTON)
    return client.call("current_page")
