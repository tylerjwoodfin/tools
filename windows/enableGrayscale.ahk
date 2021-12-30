RegRead, IsActive, HKEY_CURRENT_USER\Software\Microsoft\ColorFiltering, Active

if (!IsActive) {
    Send, #^c
    Goto Check
}

Check:
InputBox, UserInput, Time for Bed, Please take your medicine (including Melatonin) and enter the phrase "I have taken Melatonin"., , 480, 160
if ErrorLevel {
    MsgBox, Shutting Down
    ; Shutdown, 1
}
else if(UserInput == "I have taken Melatonin") {
    MsgBox, Thank you!
    Send, #^c
}
else {
    MsgBox, %UserInput%
    MsgBox, UserInput = I have taken Melatonin
    Goto Check
}