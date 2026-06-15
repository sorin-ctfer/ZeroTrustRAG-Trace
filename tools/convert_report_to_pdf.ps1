$ErrorActionPreference = "Stop"

$docxPath = $args[0]
$pdfPath = $args[1]

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $document = $word.Documents.Open($docxPath)
    $document.Fields.Update() | Out-Null
    foreach ($toc in $document.TablesOfContents) {
        $toc.Update() | Out-Null
    }
    $document.Save()
    $pdfFormat = 17
    $document.ExportAsFixedFormat($pdfPath, $pdfFormat)
    $document.Close()
}
finally {
    $word.Quit()
}
