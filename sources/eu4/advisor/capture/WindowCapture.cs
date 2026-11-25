using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

namespace Eu4Capture;

// Windows.Graphics.Capture and D3D11 ABI bindings. Capture is created for one HWND
// and its GPU surface is read back without including the desktop or other windows.
internal static class WindowCapture
{
    private const int Bgra8 = 87;
    private const uint HardwareDriver = 1;
    private const uint BgraSupport = 0x20;
    private const uint D3d11SdkVersion = 7;
    private const uint Staging = 3;
    private const uint CpuRead = 0x20000;
    private const uint MapRead = 1;
    private const int ChangedApartment = unchecked((int)0x80010106);
    private static readonly Guid CaptureInterop = new("3628e81b-3cac-4c60-b7f4-23ce0e0c3356");
    private static readonly Guid CaptureItem = new("79c3f95b-31f7-4ec2-a464-632ef5d30760");
    private static readonly Guid FramePoolStatics2 = new("589b103f-6bbc-5df5-a991-02e28b3b66d5");
    private static readonly Guid DxgiDevice = new("54ec77fa-1377-44e6-8c32-88fd5f44c84c");
    private static readonly Guid DxgiInterfaceAccess = new("a9b3d012-3df2-4ee3-b8d1-8695f457d3c1");
    private static readonly Guid Texture2D = new("6f15aaf2-d208-4e89-9ab4-489535d34f9c");
    private static readonly Guid Closable = new("30d5a829-7fa4-4026-83bb-d75bae4ea99e");

    public static Bitmap Capture(nint window, Rectangle client, Rectangle[] windowBounds)
    {
        int apartment = RoInitialize(Thread.CurrentThread.GetApartmentState() == ApartmentState.STA ? 0u : 1u);
        if (apartment != ChangedApartment)
            Check(apartment);
        try
        {
            using ComRef itemFactory = GetFactory("Windows.Graphics.Capture.GraphicsCaptureItem", CaptureInterop);
            Check(Slot<CreateForWindow>(itemFactory, 3)(itemFactory.Handle, window, in CaptureItem, out nint itemHandle));
            using var item = new ComRef(itemHandle);
            Check(Slot<GetSize>(item, 7)(item.Handle, out FrameSize size)); // IGraphicsCaptureItem::get_Size
            if (size.Width <= 0 || size.Height <= 0 || size.Width > 16384 || size.Height > 16384)
                throw Unavailable();

            Rectangle outerBounds = windowBounds.FirstOrDefault(bounds =>
                bounds.Width == size.Width && bounds.Height == size.Height && bounds.Contains(client));
            if (outerBounds.IsEmpty)
                throw new InvalidOperationException("Nie udało się dopasować obrazu do obszaru gry. Spróbuj ponownie po zmianie trybu wyświetlania.");
            var crop = new Rectangle(client.Left - outerBounds.Left, client.Top - outerBounds.Top,
                client.Width, client.Height);

            Check(D3D11CreateDevice(0, HardwareDriver, 0, BgraSupport, 0, 0, D3d11SdkVersion,
                out nint deviceHandle, 0, out nint contextHandle));
            using var device = new ComRef(deviceHandle);
            using var context = new ComRef(contextHandle);
            using ComRef dxgiDevice = device.Query(in DxgiDevice);
            Check(CreateDirect3D11DeviceFromDXGIDevice(dxgiDevice.Handle, out nint direct3DHandle));
            using var direct3D = new ComRef(direct3DHandle);
            using ComRef poolFactory = GetFactory("Windows.Graphics.Capture.Direct3D11CaptureFramePool", FramePoolStatics2);
            // IDirect3D11CaptureFramePoolStatics2::CreateFreeThreaded
            Check(Slot<CreateFramePool>(poolFactory, 6)(poolFactory.Handle, direct3D.Handle,
                Bgra8, 1, size, out nint poolHandle));
            using var pool = new ComRef(poolHandle, close: true);
            // IDirect3D11CaptureFramePool::CreateCaptureSession
            Check(Slot<CreateSession>(pool, 10)(pool.Handle, item.Handle, out nint sessionHandle));
            using var session = new ComRef(sessionHandle, close: true);
            Check(Slot<Call>(session, 6)(session.Handle)); // IGraphicsCaptureSession::StartCapture
            using ComRef frame = WaitForFrame(pool);
            Check(Slot<GetSize>(frame, 8)(frame.Handle, out FrameSize contentSize)); // get_ContentSize
            if (contentSize.Width != size.Width || contentSize.Height != size.Height)
                throw new InvalidOperationException("Rozmiar obrazu zmienił się podczas przechwytywania. Spróbuj ponownie.");
            Check(Slot<GetObject>(frame, 6)(frame.Handle, out nint surfaceHandle)); // get_Surface
            using var surface = new ComRef(surfaceHandle);
            using ComRef surfaceAccess = surface.Query(in DxgiInterfaceAccess);
            Check(Slot<GetInterface>(surfaceAccess, 3)(surfaceAccess.Handle, in Texture2D, out nint textureHandle));
            using var texture = new ComRef(textureHandle);
            return ReadPixels(device, context, texture, crop);
        }
        finally
        {
            if (apartment >= 0)
                RoUninitialize();
        }
    }

    private static ComRef WaitForFrame(ComRef pool)
    {
        var tryGetNext = Slot<GetObject>(pool, 7); // IDirect3D11CaptureFramePool::TryGetNextFrame
        var wait = Stopwatch.StartNew();
        while (wait.ElapsedMilliseconds < 650)
        {
            Check(tryGetNext(pool.Handle, out nint frame));
            if (frame != 0)
                return new ComRef(frame, close: true);
            Thread.Sleep(10);
        }
        throw Unavailable();
    }

    private static Bitmap ReadPixels(ComRef device, ComRef context, ComRef texture, Rectangle crop)
    {
        Slot<GetTextureDesc>(texture, 10)(texture.Handle, out TextureDesc desc); // ID3D11Texture2D::GetDesc
        if (desc.Format != Bgra8 || desc.Width < crop.Right || desc.Height < crop.Bottom ||
            desc.MipLevels != 1 || desc.ArraySize != 1 || desc.SampleCount != 1)
            throw Unavailable();

        desc.Usage = Staging;
        desc.BindFlags = 0;
        desc.CpuAccessFlags = CpuRead;
        desc.MiscFlags = 0;
        // ID3D11Device::CreateTexture2D, then ID3D11DeviceContext::CopyResource.
        Check(Slot<CreateTexture>(device, 5)(device.Handle, in desc, 0, out nint stagingHandle));
        using var staging = new ComRef(stagingHandle);
        Slot<CopyResource>(context, 47)(context.Handle, staging.Handle, texture.Handle);
        Check(Slot<Map>(context, 14)(context.Handle, staging.Handle, 0, MapRead, 0, out MappedResource mapped));
        try
        {
            int pitch = checked((int)mapped.RowPitch);
            nint firstPixel = mapped.Data + crop.Top * pitch + crop.Left * 4;
            using var pixels = new Bitmap(crop.Width, crop.Height, pitch, PixelFormat.Format32bppRgb, firstPixel);
            return pixels.Clone(new Rectangle(0, 0, crop.Width, crop.Height), PixelFormat.Format32bppRgb);
        }
        finally
        {
            Slot<Unmap>(context, 15)(context.Handle, staging.Handle, 0);
        }
    }

    private static InvalidOperationException Unavailable() => new(
        "Windows nie udostępnił aktualnego obrazu gry. Ustaw tryb okienkowy lub okienkowy bez ramek i spróbuj ponownie.");

    private static ComRef GetFactory(string className, Guid iid)
    {
        Check(WindowsCreateString(className, (uint)className.Length, out nint classId));
        try
        {
            Check(RoGetActivationFactory(classId, in iid, out nint factory));
            return new ComRef(factory);
        }
        finally
        {
            WindowsDeleteString(classId);
        }
    }

    private static T Slot<T>(ComRef reference, int index) where T : Delegate =>
        Marshal.GetDelegateForFunctionPointer<T>(Marshal.ReadIntPtr(Marshal.ReadIntPtr(reference.Handle), IntPtr.Size * index));

    private static void Check(int result)
    {
        if (result < 0)
            throw new COMException($"Windows Graphics Capture HRESULT 0x{result:X8}", result);
    }

    private sealed class ComRef(nint handle, bool close = false) : IDisposable
    {
        public nint Handle { get; private set; } = handle;

        public ComRef Query(in Guid id)
        {
            Guid interopId = id;
            Check(Marshal.QueryInterface(Handle, ref interopId, out nint result));
            return new ComRef(result);
        }

        public void Dispose()
        {
            if (Handle == 0)
                return;
            try
            {
                if (!close)
                    return;
                Guid id = Closable;
                if (Marshal.QueryInterface(Handle, ref id, out nint closableHandle) >= 0)
                {
                    using var closable = new ComRef(closableHandle);
                    Slot<Call>(closable, 6)(closable.Handle); // IClosable::Close
                }
            }
            finally
            {
                Marshal.Release(Handle);
                Handle = 0;
            }
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct FrameSize
    {
        public int Width, Height;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct TextureDesc
    {
        public uint Width, Height, MipLevels, ArraySize, Format, SampleCount, SampleQuality,
            Usage, BindFlags, CpuAccessFlags, MiscFlags;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MappedResource
    {
        public nint Data;
        public uint RowPitch, DepthPitch;
    }

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int CreateForWindow(nint self, nint window, in Guid iid, out nint item);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int GetSize(nint self, out FrameSize size);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int CreateFramePool(nint self, nint device, int format, int count, FrameSize size, out nint pool);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int CreateSession(nint self, nint item, out nint session);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int Call(nint self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int GetObject(nint self, out nint result);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int GetInterface(nint self, in Guid id, out nint result);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate void GetTextureDesc(nint self, out TextureDesc desc);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int CreateTexture(nint self, in TextureDesc desc, nint initialData, out nint texture);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate void CopyResource(nint self, nint dest, nint source);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int Map(nint self, nint resource, uint subresource, uint mapType, uint mapFlags, out MappedResource data);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate void Unmap(nint self, nint resource, uint subresource);

    [DllImport("combase.dll")] private static extern int RoInitialize(uint type);
    [DllImport("combase.dll")] private static extern void RoUninitialize();
    [DllImport("combase.dll", CharSet = CharSet.Unicode)]
    private static extern int WindowsCreateString(string source, uint length, out nint value);
    [DllImport("combase.dll")] private static extern int WindowsDeleteString(nint value);
    [DllImport("combase.dll")] private static extern int RoGetActivationFactory(nint classId, in Guid iid, out nint factory);
    [DllImport("d3d11.dll")]
    private static extern int D3D11CreateDevice(nint adapter, uint driver, nint software, uint flags,
        nint featureLevels, uint featureLevelCount, uint sdkVersion, out nint device, nint featureLevel, out nint context);
    [DllImport("d3d11.dll")]
    private static extern int CreateDirect3D11DeviceFromDXGIDevice(nint dxgiDevice, out nint device);
}
