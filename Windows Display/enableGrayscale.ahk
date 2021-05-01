RegRead, IsActive, HKEY_CURRENT_USER\Software\Microsoft\ColorFiltering, Active

if (!IsActive) {
    Send, #^c
}