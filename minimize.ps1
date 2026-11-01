Add-Type -Namespace Win -Name Native -MemberDefinition '[DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow(); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);'
[Win.Native]::ShowWindow([Win.Native]::GetConsoleWindow(), 6) | Out-Null
