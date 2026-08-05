[CmdletBinding(DefaultParameterSetName = 'Process')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Process')]
    [int]$ProcessId,
    [Parameter(Mandatory, ParameterSetName = 'Title')]
    [string]$TitleSubstring,
    [Parameter(Mandatory, ParameterSetName = 'Window')]
    [string]$WindowTitleSubstring,
    [Parameter(Mandatory)]
    [string]$OutputDirectory,
    [ValidateRange(1, 300)]
    [int]$DurationSeconds = 10,
    [ValidateRange(1, 60)]
    [int]$FramesPerSecond = 12,
    [switch]$CreateVideo,
    [string]$FfmpegPath,
    [string]$ReadyFile,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

if ($PSCmdlet.ParameterSetName -eq 'Process') {
    $target = Get-Process -Id $ProcessId
    $windowHandle = [IntPtr]$target.MainWindowHandle
} elseif ($PSCmdlet.ParameterSetName -eq 'Title') {
    $target = Get-Process | Where-Object { $_.MainWindowTitle -like "*$TitleSubstring*" } | Select-Object -First 1
    if (-not $target) { throw "No process window matched title substring: $TitleSubstring" }
    $windowHandle = [IntPtr]$target.MainWindowHandle
} else {
    if (-not ('JTools.WindowFinder' -as [type])) {
        Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
namespace JTools {
    public sealed class WindowMatch { public IntPtr Hwnd; public int ProcessId; public string Title; }
    public static class WindowFinder {
        private delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lParam);
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hwnd);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int maxCount);
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
        public static WindowMatch Find(string needle) {
            WindowMatch result = null;
            string lowerNeedle = needle.ToLowerInvariant();
            EnumWindows((hwnd, unused) => {
                if (!IsWindowVisible(hwnd) || result != null) return true;
                StringBuilder text = new StringBuilder(512);
                int length = GetWindowText(hwnd, text, text.Capacity);
                string title = text.ToString(0, length);
                if (title.ToLowerInvariant().Contains(lowerNeedle)) {
                    uint processId;
                    GetWindowThreadProcessId(hwnd, out processId);
                    result = new WindowMatch { Hwnd = hwnd, ProcessId = (int)processId, Title = title };
                }
                return true;
            }, IntPtr.Zero);
            return result;
        }
    }
}
'@
    }
    $match = [JTools.WindowFinder]::Find($WindowTitleSubstring)
    if (-not $match) { throw "No visible top-level window matched title substring: $WindowTitleSubstring" }
    $target = Get-Process -Id $match.ProcessId
    $windowHandle = $match.Hwnd
}

if ($windowHandle -eq [IntPtr]::Zero -or [string]::IsNullOrWhiteSpace($target.MainWindowTitle)) {
    throw "Target process has no visible top-level window: $($target.Id)"
}

$outputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$framesDirectory = Join-Path $outputDirectory 'frames'
New-Item -ItemType Directory -Force -Path $framesDirectory | Out-Null
Get-ChildItem -LiteralPath $framesDirectory -Filter 'frame_*.*' -ErrorAction SilentlyContinue | Remove-Item -Force

$sdkVersion = (Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\Include' -Directory | Sort-Object Name -Descending | Select-Object -First 1).Name
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10\Include\$sdkVersion"
$vsDevCmd = @(
    'D:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $vsDevCmd) { throw 'Visual Studio 2022 developer environment was not found.' }

$cacheRoot = Join-Path $env:LOCALAPPDATA 'JTools\wgc-temporal-evidence'
New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
$sourcePath = Join-Path $cacheRoot 'wgc_temporal_capture.cpp'
$exePath = Join-Path $cacheRoot 'wgc_temporal_capture.exe'

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
#include <chrono>
#include <filesystem>
#include <iomanip>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace winrt;
using namespace std::chrono;

void SaveBmp(const std::wstring& path, ID3D11DeviceContext* context, ID3D11Texture2D* texture, int width, int height) {
    D3D11_TEXTURE2D_DESC desc{};
    texture->GetDesc(&desc);
    desc.BindFlags = 0;
    desc.MiscFlags = 0;
    desc.Usage = D3D11_USAGE_STAGING;
    desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;

    com_ptr<ID3D11Device> device;
    texture->GetDevice(device.put());
    com_ptr<ID3D11Texture2D> staging;
    check_hresult(device->CreateTexture2D(&desc, nullptr, staging.put()));
    context->CopyResource(staging.get(), texture);

    D3D11_MAPPED_SUBRESOURCE mapped{};
    check_hresult(context->Map(staging.get(), 0, D3D11_MAP_READ, 0, &mapped));
    const UINT rowBytes = static_cast<UINT>(width) * 4;
    std::vector<uint8_t> pixels(static_cast<size_t>(rowBytes) * height);
    for (int row = 0; row < height; ++row) {
        memcpy(pixels.data() + static_cast<size_t>(row) * rowBytes,
               static_cast<const uint8_t*>(mapped.pData) + static_cast<size_t>(row) * mapped.RowPitch,
               rowBytes);
    }
    context->Unmap(staging.get(), 0);

    BITMAPFILEHEADER fileHeader{};
    BITMAPINFOHEADER infoHeader{};
    fileHeader.bfType = 0x4D42;
    fileHeader.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
    fileHeader.bfSize = fileHeader.bfOffBits + static_cast<DWORD>(pixels.size());
    infoHeader.biSize = sizeof(BITMAPINFOHEADER);
    infoHeader.biWidth = width;
    infoHeader.biHeight = -height;
    infoHeader.biPlanes = 1;
    infoHeader.biBitCount = 32;
    infoHeader.biCompression = BI_RGB;
    infoHeader.biSizeImage = static_cast<DWORD>(pixels.size());
    std::ofstream output(path, std::ios::binary);
    output.write(reinterpret_cast<const char*>(&fileHeader), sizeof(fileHeader));
    output.write(reinterpret_cast<const char*>(&infoHeader), sizeof(infoHeader));
    output.write(reinterpret_cast<const char*>(pixels.data()), static_cast<std::streamsize>(pixels.size()));
    if (!output) throw std::runtime_error("BMP write failed");
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 7) return 2;
    init_apartment(apartment_type::multi_threaded);

    HWND hwnd = reinterpret_cast<HWND>(std::stoull(argv[1], nullptr, 0));
    const std::filesystem::path outputDirectory(argv[2]);
    const int durationMilliseconds = std::stoi(argv[3]);
    const int framesPerSecond = std::stoi(argv[4]);
    const int expectedProcessId = std::stoi(argv[5]);
    const std::filesystem::path readyFile(argv[6]);
    if (!IsWindow(hwnd) || !IsWindowVisible(hwnd)) return 3;

    DWORD actualProcessId = 0;
    GetWindowThreadProcessId(hwnd, &actualProcessId);
    if (actualProcessId != static_cast<DWORD>(expectedProcessId)) return 4;
    std::filesystem::create_directories(outputDirectory);

    com_ptr<ID3D11Device> device;
    com_ptr<ID3D11DeviceContext> context;
    D3D_FEATURE_LEVEL featureLevel{};
    check_hresult(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr,
                                    D3D11_CREATE_DEVICE_BGRA_SUPPORT, nullptr, 0,
                                    D3D11_SDK_VERSION, device.put(), &featureLevel, context.put()));
    com_ptr<IInspectable> inspectable;
    check_hresult(CreateDirect3D11DeviceFromDXGIDevice(device.as<IDXGIDevice>().get(), inspectable.put()));
    auto captureDevice = inspectable.as<winrt::Windows::Graphics::DirectX::Direct3D11::IDirect3DDevice>();
    auto interop = get_activation_factory<winrt::Windows::Graphics::Capture::GraphicsCaptureItem, IGraphicsCaptureItemInterop>();
    winrt::Windows::Graphics::Capture::GraphicsCaptureItem item{nullptr};
    check_hresult(interop->CreateForWindow(hwnd, guid_of<winrt::Windows::Graphics::Capture::GraphicsCaptureItem>(), put_abi(item)));
    const auto size = item.Size();
    auto pool = winrt::Windows::Graphics::Capture::Direct3D11CaptureFramePool::CreateFreeThreaded(
        captureDevice,
        winrt::Windows::Graphics::DirectX::DirectXPixelFormat::B8G8R8A8UIntNormalized,
        2,
        size);
    auto session = pool.CreateCaptureSession(item);
    HANDLE frameEvent = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    auto token = pool.FrameArrived([frameEvent](auto const&, auto const&) { SetEvent(frameEvent); });
    session.StartCapture();

    if (!readyFile.empty()) {
        std::filesystem::create_directories(readyFile.parent_path());
        std::ofstream ready(readyFile);
        ready << "ready";
    }

    const auto interval = milliseconds(1000 / framesPerSecond);
    const auto deadline = steady_clock::now() + milliseconds(durationMilliseconds);
    auto nextCapture = steady_clock::now();
    int frameIndex = 0;

    while (steady_clock::now() < deadline) {
        if (WaitForSingleObject(frameEvent, 1000) != WAIT_OBJECT_0) continue;
        auto frame = pool.TryGetNextFrame();
        if (!frame) continue;
        const auto contentSize = frame.ContentSize();
        if (contentSize.Width != size.Width || contentSize.Height != size.Height) return 5;
        const auto now = steady_clock::now();
        if (now < nextCapture) continue;

        auto access = frame.Surface().as<::Windows::Graphics::DirectX::Direct3D11::IDirect3DDxgiInterfaceAccess>();
        com_ptr<ID3D11Texture2D> texture;
        check_hresult(access->GetInterface(__uuidof(ID3D11Texture2D), texture.put_void()));
        std::wstringstream filename;
        filename << L"frame_" << std::setw(6) << std::setfill(L'0') << frameIndex << L".bmp";
        SaveBmp((outputDirectory / filename.str()).wstring(), context.get(), texture.get(), size.Width, size.Height);
        ++frameIndex;
        nextCapture += interval;
        if (nextCapture < now - interval) nextCapture = now + interval;
    }

    pool.FrameArrived(token);
    session = nullptr;
    pool = nullptr;
    CloseHandle(frameEvent);
    std::wcout << L"WGC_RECORD_OK hwnd=0x" << std::hex << reinterpret_cast<uintptr_t>(hwnd)
               << std::dec << L" width=" << size.Width << L" height=" << size.Height
               << L" frames=" << frameIndex << L"\n";
    return frameIndex > 0 ? 0 : 6;
}
'@

if (-not (Test-Path $sourcePath) -or (Get-Content -Raw $sourcePath) -ne $source -or -not (Test-Path $exePath)) {
    Set-Content -LiteralPath $sourcePath -Value $source -Encoding Ascii
    $compile = "call `"$vsDevCmd`" -arch=x64 -host_arch=x64 && cl /nologo /std:c++20 /EHsc /I`"$sdkRoot\cppwinrt`" /I`"$sdkRoot\um`" /I`"$sdkRoot\shared`" `"$sourcePath`" /Fe:`"$exePath`" /link d3d11.lib dxgi.lib windowscodecs.lib windowsapp.lib user32.lib ole32.lib"
    cmd /c $compile | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "WGC recorder compilation failed with exit code $LASTEXITCODE." }
}

$windowHandle = $windowHandle.ToInt64()
$durationMilliseconds = $DurationSeconds * 1000
if ($ReadyFile) {
    $ReadyFile = [IO.Path]::GetFullPath($ReadyFile)
    if (Test-Path -LiteralPath $ReadyFile) { Remove-Item -LiteralPath $ReadyFile -Force }
} else {
    $ReadyFile = ''
}
& $exePath $windowHandle $framesDirectory $durationMilliseconds $FramesPerSecond $target.Id $ReadyFile | Out-Host
if ($LASTEXITCODE -ne 0) { throw "WGC recording failed with exit code $LASTEXITCODE." }

$frames = @(Get-ChildItem -LiteralPath $framesDirectory -Filter 'frame_*.bmp' | Sort-Object Name)
if ($frames.Count -eq 0) { throw 'WGC recording produced no frames.' }

Add-Type -AssemblyName System.Drawing
$firstFrame = [Drawing.Bitmap]::FromFile($frames[0].FullName)
$width = $firstFrame.Width
$height = $firstFrame.Height
$firstFrame.Dispose()

$videoPath = $null
if ($CreateVideo) {
    if (-not $FfmpegPath) {
        $FfmpegPath = (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    }
    if (-not $FfmpegPath) { throw 'ffmpeg.exe was not found. Pass -FfmpegPath explicitly.' }
    $videoPath = Join-Path $outputDirectory 'recording.mp4'
    & $FfmpegPath -y -hide_banner -loglevel error -framerate $FramesPerSecond -i (Join-Path $framesDirectory 'frame_%06d.bmp') -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p $videoPath
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed with exit code $LASTEXITCODE." }
}

$metadata = [ordered]@{
    success = $true
    captureMode = 'windows_graphics_capture_sequence'
    processId = $target.Id
    windowTitle = $target.MainWindowTitle
    windowHandle = ('0x{0:X}' -f $windowHandle)
    durationSeconds = $DurationSeconds
    requestedFramesPerSecond = $FramesPerSecond
    capturedFrameCount = $frames.Count
    effectiveFramesPerSecond = [Math]::Round($frames.Count / $DurationSeconds, 3)
    width = $width
    height = $height
    framesDirectory = $framesDirectory
    videoPath = $videoPath
    capturedAt = (Get-Date).ToString('o')
    readyFile = if ($ReadyFile) { $ReadyFile } else { $null }
}
$metadataPath = Join-Path $outputDirectory 'recording.json'
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8
if ($Json) { $metadata | ConvertTo-Json }
