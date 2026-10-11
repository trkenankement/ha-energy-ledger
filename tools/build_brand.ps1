# Render the original vector-style mark with Windows' built-in drawing library.
# No network access or additional production dependencies.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$brandRoot = Join-Path (Split-Path -Parent $PSScriptRoot) 'custom_components/energy_ledger/brand'
New-Item -ItemType Directory -Path $brandRoot -Force | Out-Null
foreach ($size in 256, 512) {
    $bitmap = [Drawing.Bitmap]::new($size, $size)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([Drawing.Color]::Transparent)
    $graphics.ScaleTransform($size / 256.0, $size / 256.0)
    $background = [Drawing.Drawing2D.GraphicsPath]::new()
    foreach ($arc in @(@(12,12,64,64,180,90), @(180,12,64,64,270,90),
                       @(180,180,64,64,0,90), @(12,180,64,64,90,90))) {
        $background.AddArc($arc[0],$arc[1],$arc[2],$arc[3],$arc[4],$arc[5])
    }
    $background.CloseFigure()
    $gradient = [Drawing.Drawing2D.LinearGradientBrush]::new(
        [Drawing.Point]::new(16,16), [Drawing.Point]::new(240,240),
        [Drawing.ColorTranslator]::FromHtml('#123C53'),
        [Drawing.ColorTranslator]::FromHtml('#102533'))
    $graphics.FillPath($gradient, $background)
    $ink = [Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml('#E7F5F5'), 10)
    $ink.LineJoin = [Drawing.Drawing2D.LineJoin]::Round
    $ink.StartCap = $ink.EndCap = [Drawing.Drawing2D.LineCap]::Round
    $page = [Drawing.Drawing2D.GraphicsPath]::new()
    $page.AddLines([Drawing.PointF[]]@(
        [Drawing.PointF]::new(77,55), [Drawing.PointF]::new(158,55),
        [Drawing.PointF]::new(181,78), [Drawing.PointF]::new(181,199),
        [Drawing.PointF]::new(77,199), [Drawing.PointF]::new(77,55)))
    $graphics.DrawPath($ink, $page)
    $graphics.DrawLine($ink, 158,55,158,80)
    $graphics.DrawLine($ink, 158,80,181,80)
    $binding = [Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml('#54DCC3'), 7)
    $binding.StartCap = $binding.EndCap = [Drawing.Drawing2D.LineCap]::Round
    foreach ($y in 82,110,138,166) { $graphics.DrawLine($binding,64,$y,83,$y) }
    $bolt = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml('#54DCC3'))
    $graphics.FillPolygon($bolt, [Drawing.PointF[]]@(
        [Drawing.PointF]::new(141,91),[Drawing.PointF]::new(104,139),
        [Drawing.PointF]::new(129,139),[Drawing.PointF]::new(116,172),
        [Drawing.PointF]::new(157,123),[Drawing.PointF]::new(133,123)))
    $filename = if ($size -eq 256) { 'icon.png' } else { 'icon@2x.png' }
    $bitmap.Save((Join-Path $brandRoot $filename), [Drawing.Imaging.ImageFormat]::Png)
    # The self-contained dark tile has the same contrast on both HA themes.
    Copy-Item -LiteralPath (Join-Path $brandRoot $filename) -Destination (Join-Path $brandRoot ('dark_'+$filename)) -Force
    $bolt.Dispose(); $binding.Dispose(); $page.Dispose(); $ink.Dispose()
    $gradient.Dispose(); $background.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}
