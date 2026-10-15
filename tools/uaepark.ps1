# Move the WinUAE window off-screen without activating it, so reference captures
# (winshot.ps1 uses PrintWindow) can run while the desktop is in use.
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class WP {
  [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
}
"@
$h = [WP]::FindWindow("PCsuxRox", [NullString]::Value)
if ($h -eq [IntPtr]::Zero) { throw "WinUAE window not found" }
[WP]::ShowWindow($h, 4) | Out-Null                       # SW_SHOWNOACTIVATE (restore if minimized)
# HWND_BOTTOM, SWP_NOSIZE | SWP_NOACTIVATE
[WP]::SetWindowPos($h, [IntPtr]1, -4000, 0, 0, 0, 0x0001 -bor 0x0010) | Out-Null
"parked"
