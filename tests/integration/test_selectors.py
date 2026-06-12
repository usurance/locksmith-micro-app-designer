from driver import selectors as S


def test_static_selectors_present():
    assert S.Toolbar.VAULTS_BUTTON == "toolbar.vaultsButton"
    assert S.VaultDrawer.NEW_VAULT_ITEM == "Initialize New Vault"
    assert S.CreateVaultDialog.PASSCODE == "createVaultDialog.passcodeField"
    assert S.OpenVaultDialog.OPEN == "openVaultDialog.openButton"
    assert S.Designer.NAV_BUTTON == "designer.navButton"


def test_per_vault_selectors_interpolate_name():
    assert S.VaultDrawer.open_button("automation") == "vaultDrawer.open.automation"
    assert S.VaultDrawer.row("automation") == "vaultDrawer.row.automation"
