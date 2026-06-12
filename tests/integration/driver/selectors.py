"""Layer 1: page objects — the living selector cheatsheet.

Each class groups the objectNames (or list-item text) for one screen, plus the
op each control needs in a comment. Curated from the host source once per
screen. Actions and tests import from here so selectors never drift.
"""
from __future__ import annotations


class Toolbar:
    VAULTS_BUTTON = "toolbar.vaultsButton"   # click — opens the Vaults drawer


class VaultDrawer:
    NEW_VAULT_ITEM = "Initialize New Vault"  # QListWidget item -> click_list_item
    VAULT_LIST = "vaultDrawer.vaultList"     # count / get_list_items

    @staticmethod
    def open_button(name: str) -> str:
        return f"vaultDrawer.open.{name}"    # click — opens the unlock dialog

    @staticmethod
    def close_button(name: str) -> str:
        return f"vaultDrawer.close.{name}"   # click — closes the currently-open vault

    @staticmethod
    def row(name: str) -> str:
        return f"vaultDrawer.row.{name}"


class CreateVaultDialog:
    NAME = "createVaultDialog.nameField"         # type
    PASSCODE = "createVaultDialog.passcodeField" # type
    CREATE = "createVaultDialog.createButton"    # click
    CANCEL = "createVaultDialog.cancelButton"    # click


class OpenVaultDialog:
    PASSCODE = "openVaultDialog.passcodeField"   # type
    OPEN = "openVaultDialog.openButton"          # click
    CANCEL = "openVaultDialog.cancelButton"      # click


class Designer:
    NAV_BUTTON = "designer.navButton"                      # click — enters the plugin (set in plugin.py)
    TEMPLATES_NAV_BUTTON = "designer.templatesNavButton"   # click — in-plugin templates entry (set in plugin.py)
    PAGE_OVERVIEW = "designer.overview"                    # current_page value
    PAGE_TEMPLATES = "designer.templates"                  # current_page value
