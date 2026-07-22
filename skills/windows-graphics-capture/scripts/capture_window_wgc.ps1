[CmdletBinding(DefaultParameterSetName = 'Title')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Title')]
    [string]$TitleSubstring,
    [Parameter(Mandatory, ParameterSetName = 'Process')]
    [int]$ProcessId,
    [Parameter(Mandatory)]
    [string]$OutputPath,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

if ($PSCmdlet.ParameterSetName -eq 'Process') {
    $process = Get-Process -Id $ProcessId
    if ($process.MainWindowHandle -eq 0 -or [string]::IsNullOrWhiteSpace($process.MainWindowTitle)) {
        throw "Process $ProcessId has no visible top-level window."
    }
    $TitleSubstring = $process.MainWindowTitle
}

$outputPath = [IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$bmpPath = [IO.Path]::ChangeExtension($outputPath, '.wgc-tmp.bmp')
$metadataPath = [IO.Path]::ChangeExtension($outputPath, '.json')

$sdkVersion = (Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\Include' -Directory | Sort-Object Name -Descending | Select-Object -First 1).Name
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10\Include\$sdkVersion"
$vsDevCmd = 'D:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat'
if (-not (Test-Path $vsDevCmd)) { throw "Visual Studio developer environment not found: $vsDevCmd" }

$cacheRoot = Join-Path $env:TEMP 'codex-wgc-capture'
New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
$sourcePath = Join-Path $cacheRoot 'wgc_capture.cpp'
$exePath = Join-Path $cacheRoot 'wgc_capture.exe'

$source = @'
#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <windows.graphics.capture.interop.h>
#include <windows.graphics.directx.direct3d11.interop.h>
#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Graphics.Capture.h>
#include <winrt/Windows.Graphics.DirectX.h>
#include <winrt/Windows.Graphics.DirectX.Direct3D11.h>
#include <algorithm>
#include <cwctype>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
using namespace winrt;
struct Search { std::wstring needle; HWND hwnd = nullptr; };
std::wstring Lower(std::wstring v) { std::transform(v.begin(), v.end(), v.begin(), towlower); return v; }
BOOL CALLBACK Find(HWND hwnd, LPARAM p) { auto* s = reinterpret_cast<Search*>(p); if (!IsWindowVisible(hwnd)) return TRUE; int n = GetWindowTextLengthW(hwnd); if (!n) return TRUE; std::wstring title(n + 1, L'\0'); GetWindowTextW(hwnd, title.data(), n + 1); title.resize(n); if (Lower(title).find(s->needle) != std::wstring::npos) { s->hwnd = hwnd; return FALSE; } return TRUE; }
void Bmp(const std::wstring& path, ID3D11DeviceContext* context, ID3D11Texture2D* texture, int width, int height) { D3D11_TEXTURE2D_DESC d{}; texture->GetDesc(&d); d.BindFlags = 0; d.MiscFlags = 0; d.Usage = D3D11_USAGE_STAGING; d.CPUAccessFlags = D3D11_CPU_ACCESS_READ; com_ptr<ID3D11Device> device; texture->GetDevice(device.put()); com_ptr<ID3D11Texture2D> staging; check_hresult(device->CreateTexture2D(&d, nullptr, staging.put())); context->CopyResource(staging.get(), texture); D3D11_MAPPED_SUBRESOURCE m{}; check_hresult(context->Map(staging.get(), 0, D3D11_MAP_READ, 0, &m)); uint32_t rowBytes = width * 4; std::vector<uint8_t> pixels(static_cast<size_t>(rowBytes) * height); for (int row = 0; row < height; ++row) memcpy(pixels.data() + static_cast<size_t>(height - 1 - row) * rowBytes, static_cast<const uint8_t*>(m.pData) + static_cast<size_t>(row) * m.RowPitch, rowBytes); context->Unmap(staging.get(), 0); BITMAPFILEHEADER f{}; BITMAPINFOHEADER i{}; f.bfType = 0x4D42; f.bfOffBits = sizeof(f) + sizeof(i); f.bfSize = f.bfOffBits + static_cast<DWORD>(pixels.size()); i.biSize = sizeof(i); i.biWidth = width; i.biHeight = height; i.biPlanes = 1; i.biBitCount = 32; i.biCompression = BI_RGB; std::ofstream out(path, std::ios::binary); out.write(reinterpret_cast<const char*>(&f), sizeof(f)); out.write(reinterpret_cast<const char*>(&i), sizeof(i)); out.write(reinterpret_cast<const char*>(pixels.data()), pixels.size()); }
int wmain(int argc, wchar_t** argv) { if (argc != 3) return 2; init_apartment(apartment_type::multi_threaded); Search s{Lower(argv[1])}; EnumWindows(Find, reinterpret_cast<LPARAM>(&s)); if (!s.hwnd) return 3; com_ptr<ID3D11Device> device; com_ptr<ID3D11DeviceContext> context; D3D_FEATURE_LEVEL level{}; check_hresult(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, D3D11_CREATE_DEVICE_BGRA_SUPPORT, nullptr, 0, D3D11_SDK_VERSION, device.put(), &level, context.put())); com_ptr<IInspectable> inspectable; check_hresult(CreateDirect3D11DeviceFromDXGIDevice(device.as<IDXGIDevice>().get(), inspectable.put())); auto captureDevice = inspectable.as<winrt::Windows::Graphics::DirectX::Direct3D11::IDirect3DDevice>(); auto interop = get_activation_factory<winrt::Windows::Graphics::Capture::GraphicsCaptureItem, IGraphicsCaptureItemInterop>(); winrt::Windows::Graphics::Capture::GraphicsCaptureItem item{nullptr}; check_hresult(interop->CreateForWindow(s.hwnd, guid_of<winrt::Windows::Graphics::Capture::GraphicsCaptureItem>(), put_abi(item))); auto size = item.Size(); auto pool = winrt::Windows::Graphics::Capture::Direct3D11CaptureFramePool::CreateFreeThreaded(captureDevice, winrt::Windows::Graphics::DirectX::DirectXPixelFormat::B8G8R8A8UIntNormalized, 1, size); auto session = pool.CreateCaptureSession(item); HANDLE event = CreateEventW(nullptr, TRUE, FALSE, nullptr); auto token = pool.FrameArrived([event](auto const&, auto const&) { SetEvent(event); }); session.StartCapture(); if (WaitForSingleObject(event, 5000) != WAIT_OBJECT_0) return 4; auto frame = pool.TryGetNextFrame(); auto access = frame.Surface().as<::Windows::Graphics::DirectX::Direct3D11::IDirect3DDxgiInterfaceAccess>(); com_ptr<ID3D11Texture2D> texture; check_hresult(access->GetInterface(__uuidof(ID3D11Texture2D), texture.put_void())); Bmp(argv[2], context.get(), texture.get(), size.Width, size.Height); std::wcout << L"WGC_CAPTURE_OK hwnd=0x" << std::hex << reinterpret_cast<uintptr_t>(s.hwnd) << std::dec << L" width=" << size.Width << L" height=" << size.Height << L"\n"; return 0; }
'@

if (-not (Test-Path $sourcePath) -or (Get-Content -Raw $sourcePath) -ne $source -or -not (Test-Path $exePath)) {
    Set-Content -LiteralPath $sourcePath -Value $source -Encoding Ascii
    $compile = "call `"$vsDevCmd`" -arch=x64 -host_arch=x64 && cl /nologo /std:c++20 /EHsc /I`"$sdkRoot\cppwinrt`" /I`"$sdkRoot\um`" /I`"$sdkRoot\shared`" `"$sourcePath`" /Fe:`"$exePath`" /link d3d11.lib dxgi.lib windowsapp.lib user32.lib"
    cmd /c $compile | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "WGC helper compilation failed with exit code $LASTEXITCODE." }
}

& $exePath $TitleSubstring $bmpPath | Out-Host
if ($LASTEXITCODE -ne 0) { throw "WGC capture failed with exit code $LASTEXITCODE." }

Add-Type -AssemblyName System.Drawing
$bitmap = [Drawing.Bitmap]::FromFile($bmpPath)
$width = $bitmap.Width
$height = $bitmap.Height
$bitmap.Save($outputPath, [Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()
Remove-Item -LiteralPath $bmpPath -Force

$captured = Get-Item -LiteralPath $outputPath
$target = Get-Process | Where-Object { $_.MainWindowTitle -like "*$TitleSubstring*" } | Select-Object -First 1
$metadata = [ordered]@{
    success = $true
    captureMode = 'windows_graphics_capture'
    titleSubstring = $TitleSubstring
    processId = if ($target) { $target.Id } else { $null }
    windowTitle = if ($target) { $target.MainWindowTitle } else { $null }
    windowHandle = if ($target) { ('0x{0:X}' -f $target.MainWindowHandle.ToInt64()) } else { $null }
    width = $width
    height = $height
    outputPath = $outputPath
    outputSizeBytes = $captured.Length
    warning = 'WGC captures visible non-minimized windows; protected content, secure desktop, or privilege boundaries may not be capturable.'
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8
if ($Json) { $metadata | ConvertTo-Json }
