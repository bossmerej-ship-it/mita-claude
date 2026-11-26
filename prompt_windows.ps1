# One persistent UI Automation helper. Output contains geometry, never editor values.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MitaAccessibility {
    [DllImport("oleacc.dll")]
    public static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint objectId,
        ref Guid interfaceId, out IntPtr accessible);
    public static void Enable(IntPtr hwnd) {
        Guid iid = new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");
        IntPtr accessible;
        if (AccessibleObjectFromWindow(hwnd, 0xfffffffc, ref iid, out accessible) == 0
                && accessible != IntPtr.Zero) Marshal.Release(accessible);
    }
}
'@
$activated = [Collections.Generic.HashSet[long]]::new()
$editCondition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Edit)
function Rect($element) {
    $r = $element.Current.BoundingRectangle
    return ,@($r.Left, $r.Top, $r.Right, $r.Bottom)
}
while ($null -ne ($line = [Console]::ReadLine())) {
    try {
        $request = $line | ConvertFrom-Json
        $handle = [long]$request.hwnd
        if ($activated.Add($handle)) { [MitaAccessibility]::Enable([IntPtr]$handle) }
        $window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$handle)
        $bounds = Rect $window
        $edits = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editCondition)
        $candidates = @()
        foreach ($edit in $edits) {
            $current = $edit.Current
            if ($current.IsOffscreen -or -not $current.IsEnabled -or $current.IsPassword) { continue }
            $readOnly = $edit.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::IsReadOnlyProperty, $true)
            if ($readOnly -is [bool] -and $readOnly) { continue }
            $parents = @()
            $parent = $edit
            # Chromium's control view skips the painted composer and goes straight to
            # the footer that also contains file-change badges or other floating controls.
            for ($depth = 0; $depth -lt 9; $depth++) {
                $parent = [System.Windows.Automation.TreeWalker]::RawViewWalker.GetParent($parent)
                if ($null -eq $parent -or $parent.Current.ControlType -eq [System.Windows.Automation.ControlType]::Window) { break }
                $parents += @{
                    rect = (Rect $parent)
                    hint = "$($parent.Current.AutomationId) $($parent.Current.ClassName)"
                }
            }
            $candidates += @{
                rect = (Rect $edit)
                parents = $parents
                hint = "$($current.AutomationId) $($current.ClassName)"
            }
        }
        $response = @{window = $bounds; candidates = $candidates}
        [Console]::WriteLine(($response | ConvertTo-Json -Compress -Depth 6))
    } catch {
        [Console]::WriteLine('{"window":null,"candidates":[]}')
    }
}
