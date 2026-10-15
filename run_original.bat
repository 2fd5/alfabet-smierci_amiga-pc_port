@echo off
rem One-click launcher: boots the untouched Amiga original in WinUAE (A1200/AGA).
rem Disk swapping: End+1..4 inserts disk 1..4 into DF0 (WinUAE disk swapper).
set "R=%~dp0"
start "" "%R%tools\winuae\winuae64.exe" -config="%R%tools\winuae\alfabet.uae" ^
  -s floppy0="%R%AlfabetSmierci\data\disk1.adf" ^
  -s diskimage0="%R%AlfabetSmierci\data\disk1.adf" ^
  -s diskimage1="%R%AlfabetSmierci\data\disk2.adf" ^
  -s diskimage2="%R%AlfabetSmierci\data\disk3.adf" ^
  -s diskimage3="%R%AlfabetSmierci\data\disk4.adf" %*
