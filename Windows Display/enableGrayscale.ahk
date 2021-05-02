RegRead, IsActive, HKEY_CURRENT_USER\Software\Microsoft\ColorFiltering, Active

if (!IsActive) {
    Send, #^c
    MsgBox, 0, Warning, Start getting ready for bed- please take your medicine, including melatonin, then come back and click OK.
}