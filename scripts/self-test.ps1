param(
  [string]$ExePath = "$PSScriptRoot\..\src-tauri\target\release\xiaoju-desktop-pet.exe",
  [string]$LogPath = "$PSScriptRoot\..\self-test-interactions.log",
  [string]$IconFixturePath = "$PSScriptRoot\..\self-test-desktop-icons.json"
)

$ErrorActionPreference = "Stop"

$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$resolvedLog = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($LogPath)
$resolvedIconFixture = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($IconFixturePath)
Remove-Item -LiteralPath $resolvedLog -ErrorAction SilentlyContinue

function Write-DesktopIconFixture {
  param([object[]]$Icons)

  if ($Icons.Count -eq 0) {
    $json = "[]"
  } else {
    $json = ConvertTo-Json -InputObject @($Icons) -Depth 4 -Compress
  }

  [System.IO.File]::WriteAllText(
    $resolvedIconFixture,
    $json,
    [System.Text.UTF8Encoding]::new($false)
  )
}

if (-not ("WinPetSelfTest" -as [type])) {
  Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class WinPetSelfTest {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
  }

  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int X, int Y);

  [DllImport("user32.dll")]
  public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);

  [DllImport("user32.dll")]
  public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

  [DllImport("user32.dll")]
  public static extern uint GetDpiForWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern bool IsWindowVisible(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

  public static IntPtr FindVisibleWindowForProcess(int processId) {
    IntPtr found = IntPtr.Zero;
    int bestArea = 0;
    EnumWindows((hWnd, lParam) => {
      uint windowProcessId;
      GetWindowThreadProcessId(hWnd, out windowProcessId);
      if (windowProcessId == processId && IsWindowVisible(hWnd)) {
        RECT rect;
        GetWindowRect(hWnd, out rect);
        int width = rect.Right - rect.Left;
        int height = rect.Bottom - rect.Top;
        int area = width * height;
        if (width >= 100 && height >= 100 && area > bestArea) {
          found = hWnd;
          bestArea = area;
        }
      }
      return true;
    }, IntPtr.Zero);

    return found;
  }
}
"@
}

function Wait-Until {
  param(
    [scriptblock]$Condition,
    [int]$TimeoutMs,
    [string]$Description
  )

  $deadline = (Get-Date).AddMilliseconds($TimeoutMs)
  while ((Get-Date) -lt $deadline) {
    if (& $Condition) {
      return
    }
    Start-Sleep -Milliseconds 100
  }

  throw "Timed out waiting for $Description."
}

function Wait-LogContains {
  param([string]$Event)

  Wait-Until {
    if (-not (Test-Path -LiteralPath $resolvedLog)) {
      return $false
    }

    $lines = @(Get-Content -LiteralPath $resolvedLog -ErrorAction SilentlyContinue)
    return $lines -contains $Event
  } 12000 "interaction event '$Event'"
}

function Get-AppRect {
  $rect = New-Object WinPetSelfTest+RECT
  if (-not [WinPetSelfTest]::GetWindowRect($script:WindowHandle, [ref]$rect)) {
    throw "Unable to read Xiaoju window bounds."
  }
  return $rect
}

[uint32]$LeftDown = 0x0002
[uint32]$LeftUp = 0x0004
[uint32]$RightDown = 0x0008
[uint32]$RightUp = 0x0010

function Click-Left {
  param([int]$X, [int]$Y)

  [WinPetSelfTest]::SetCursorPos($X, $Y) | Out-Null
  Start-Sleep -Milliseconds 160
  [WinPetSelfTest]::mouse_event($LeftDown, 0, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 80
  [WinPetSelfTest]::mouse_event($LeftUp, 0, 0, 0, [UIntPtr]::Zero)
}

function Click-Right {
  param([int]$X, [int]$Y)

  [WinPetSelfTest]::SetCursorPos($X, $Y) | Out-Null
  Start-Sleep -Milliseconds 160
  [WinPetSelfTest]::mouse_event($RightDown, 0, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 80
  [WinPetSelfTest]::mouse_event($RightUp, 0, 0, 0, [UIntPtr]::Zero)
}

function Drag-Window {
  param(
    [int]$StartX,
    [int]$StartY,
    [int]$DeltaX,
    [int]$DeltaY
  )

  [WinPetSelfTest]::SetCursorPos($StartX, $StartY) | Out-Null
  Start-Sleep -Milliseconds 160
  [WinPetSelfTest]::mouse_event($LeftDown, 0, 0, 0, [UIntPtr]::Zero)

  1..8 | ForEach-Object {
    $x = [int]($StartX + ($DeltaX * $_ / 8))
    $y = [int]($StartY + ($DeltaY * $_ / 8))
    [WinPetSelfTest]::SetCursorPos($x, $y) | Out-Null
    Start-Sleep -Milliseconds 70
  }

  [WinPetSelfTest]::mouse_event($LeftUp, 0, 0, 0, [UIntPtr]::Zero)
}

Write-DesktopIconFixture @()

$env:XIAOJU_SELF_TEST_LOG = $resolvedLog
$env:XIAOJU_DESKTOP_ICON_FIXTURE_FILE = $resolvedIconFixture
$process = Start-Process -FilePath $resolvedExe -PassThru
Remove-Item Env:\XIAOJU_SELF_TEST_LOG -ErrorAction SilentlyContinue
Remove-Item Env:\XIAOJU_DESKTOP_ICON_FIXTURE_FILE -ErrorAction SilentlyContinue

try {
  Wait-LogContains "app_ready"

  $script:WindowHandle = [IntPtr]::Zero
  Wait-Until {
    $script:WindowHandle = [WinPetSelfTest]::FindVisibleWindowForProcess($process.Id)
    return $script:WindowHandle -ne [IntPtr]::Zero
  } 10000 "Xiaoju desktop window"

  $rect = Get-AppRect
  $windowWidth = $rect.Right - $rect.Left
  $windowHeight = $rect.Bottom - $rect.Top
  if ($windowWidth -ne 165 -or $windowHeight -ne 155) {
    throw "Unexpected Xiaoju window size. Expected 165x155, got ${windowWidth}x${windowHeight}."
  }

  $centerX = [int](($rect.Left + $rect.Right) / 2)
  $centerY = [int]($rect.Top + ($windowHeight * 0.68))

  Click-Left $centerX $centerY
  Wait-LogContains "click"

  [WinPetSelfTest]::SetCursorPos($rect.Right + 80, $rect.Top + 20) | Out-Null
  Start-Sleep -Milliseconds 300
  [WinPetSelfTest]::SetCursorPos($centerX, $centerY) | Out-Null
  Wait-LogContains "hover_eat"
  Wait-LogContains "fish_chase"
  Wait-LogContains "fish_eat"

  $beforeDrag = Get-AppRect
  $dragStartX = [int](($beforeDrag.Left + $beforeDrag.Right) / 2)
  $dragStartY = [int]($beforeDrag.Top + (($beforeDrag.Bottom - $beforeDrag.Top) * 0.68))
  Drag-Window $dragStartX $dragStartY 80 56
  Wait-LogContains "drag_start"
  Wait-LogContains "drag_end"

  Start-Sleep -Milliseconds 500
  $afterDrag = Get-AppRect
  $moveX = $afterDrag.Left - $beforeDrag.Left
  $moveY = $afterDrag.Top - $beforeDrag.Top
  if ([Math]::Abs($moveX) -lt 20 -or [Math]::Abs($moveY) -lt 12) {
    throw "Drag did not move the window far enough. Move was x=$moveX y=$moveY."
  }

  $quitX = [int](($afterDrag.Left + $afterDrag.Right) / 2)
  $quitY = [int](($afterDrag.Top + $afterDrag.Bottom) / 2)
  Click-Right $quitX $quitY
  Start-Sleep -Milliseconds 800
  if ($process.HasExited) {
    throw "Right-clicking the pet body exited Xiaoju unexpectedly."
  }

  $dpi = [WinPetSelfTest]::GetDpiForWindow($script:WindowHandle)
  $scale = if ($dpi -gt 0) { $dpi / 96 } else { 1 }
  $iconWidth = [int](74 * $scale)
  $iconHeight = [int](82 * $scale)
  $iconCenterX = ([double](($afterDrag.Left + $afterDrag.Right) / 2) * $scale) + (30 * $scale)
  $iconCenterY = ($afterDrag.Top * $scale) + ((($afterDrag.Bottom - $afterDrag.Top) * $scale) * 0.72) + (18 * $scale)
  $iconX = [int]($iconCenterX - ($iconWidth / 2))
  $iconY = [int]($iconCenterY - ($iconHeight / 2))
  Write-DesktopIconFixture @(
    [ordered]@{
      title = "Self Test App"
      x = $iconX
      y = $iconY
      width = $iconWidth
      height = $iconHeight
    }
  )
  Wait-LogContains "desktop_icon_interact"
  Wait-LogContains "desktop_icon_wrap"
  Wait-LogContains "desktop_icon_click_through_on"
  Wait-LogContains "desktop_icon_hug_pose"
  Wait-LogContains "desktop_icon_custom_hug_sprite"
  $lines = @(Get-Content -LiteralPath $resolvedLog -ErrorAction SilentlyContinue)
  if ($lines -contains "desktop_icon_snapshot") {
    throw "Desktop icon interaction copied a snapshot instead of keeping the real desktop icon visible."
  }

  Start-Sleep -Milliseconds 500
  $afterWrap = Get-AppRect
  $wrapMoveX = $afterWrap.Left - $afterDrag.Left
  $wrapMoveY = $afterWrap.Top - $afterDrag.Top
  if ([Math]::Abs($wrapMoveX) -lt 12 -or [Math]::Abs($wrapMoveY) -lt 5) {
    throw "Desktop icon wrap did not move the window far enough. Move was x=$wrapMoveX y=$wrapMoveY."
  }

  [ordered]@{
    app_ready = $true
    click = $true
    hover_eat = $true
    fish_chase = $true
    fish_eat = $true
    window_width = $windowWidth
    window_height = $windowHeight
    drag_start = $true
    drag_end = $true
    drag_move_x = $moveX
    drag_move_y = $moveY
    right_click_keeps_open = $true
    desktop_icon_interact = $true
    desktop_icon_wrap = $true
    desktop_icon_click_through_on = $true
    desktop_icon_hug_pose = $true
    desktop_icon_custom_hug_sprite = $true
    wrap_move_x = $wrapMoveX
    wrap_move_y = $wrapMoveY
    log = $resolvedLog
    icon_fixture = $resolvedIconFixture
  } | ConvertTo-Json
}
finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  }
  Remove-Item Env:\XIAOJU_SELF_TEST_LOG -ErrorAction SilentlyContinue
  Remove-Item Env:\XIAOJU_DESKTOP_ICON_FIXTURE_FILE -ErrorAction SilentlyContinue
}
