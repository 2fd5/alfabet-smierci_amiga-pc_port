# Talk to a running WinUAE over its IPC pipe (\\.\pipe\WinUAE). No keyboard/mouse hijacking.
# Commands: "CFG key value" (runtime config, space not =, e.g. floppy0 C:/x/disk2.adf), "EVT name=value" (input events),
#           "DBG cmd" (debugger command). Usage: uaeipc.ps1 "CFG floppy0 C:/x/disk2.adf" ["DBG ..."]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Commands)
$p = New-Object System.IO.Pipes.NamedPipeClientStream(".", "WinUAE", [System.IO.Pipes.PipeDirection]::InOut)
$p.Connect(3000)
$p.ReadMode = [System.IO.Pipes.PipeTransmissionMode]::Message
$buf = New-Object byte[] 65536
foreach ($c in $Commands) {
  $msg = [Text.Encoding]::ASCII.GetBytes($c + [char]0)
  $p.Write($msg, 0, $msg.Length); $p.Flush()
  $t = $p.ReadAsync($buf, 0, $buf.Length)
  if ($t.Wait(5000)) { "$c -> " + ([Text.Encoding]::ASCII.GetString($buf, 0, $t.Result)).Trim([char]0) } else { "$c -> (no reply)" }
}
$p.Dispose()
