# Capture the WinUAE emulation window (class "PCsuxRox") to a PNG without bringing it
# to the front (PrintWindow + PW_RENDERFULLCONTENT), so it works while other windows cover it.
# Usage: winshot.ps1 out.png
param([string]$Out = "winuae.png")
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WS {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@
[WS]::SetProcessDPIAware() | Out-Null
$h = [WS]::FindWindow("PCsuxRox", [NullString]::Value)
if ($h -eq [IntPtr]::Zero) { throw "WinUAE window not found" }
$r = New-Object WS+RECT
[WS]::GetClientRect($h, [ref]$r) | Out-Null
$w = $r.R - $r.L; $hh = $r.B - $r.T
$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
# 1 = PW_CLIENTONLY, 2 = PW_RENDERFULLCONTENT
[WS]::PrintWindow($h, $hdc, 3) | Out-Null
$g.ReleaseHdc($hdc)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
"$w x $hh -> $Out"
