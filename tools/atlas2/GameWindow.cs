using System.ComponentModel;
using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

namespace Atlas2;

internal sealed record GameFrame(
    byte[] Jpeg,
    nint Window,
    uint ProcessId,
    Rectangle ClientBounds,
    Size SceneSize,
    int[] Scene);

internal static class GameWindow
{
    private const int ExtendedFrameBounds = 9;
    private const int Cloaked = 14;
    private const uint RootOwner = 3;
    private static readonly ImageCodecInfo JpegEncoder = ImageCodecInfo.GetImageEncoders()
        .First(codec => codec.FormatID == ImageFormat.Jpeg.Guid);

    public static bool IsForeground()
    {
        nint window = GetForegroundWindow();
        return TryGetIdentity(window, out _);
    }

    public static GameFrame Capture()
    {
        nint window = GetForegroundWindow();
        if (!TryGetIdentity(window, out uint processId) || !TryGetClientBounds(window, out Rectangle bounds))
            throw new InvalidOperationException("Przełącz się do okna Europa Universalis IV i użyj skrótu ponownie.");

        using Bitmap bitmap = CaptureClient(window, bounds);
        Size sceneSize = Fit(bitmap.Size, 384);
        int[] scene = SampleScene(bitmap, sceneSize);
        using Bitmap image = Scale(bitmap, Fit(bitmap.Size, 1920));
        using var stream = new MemoryStream();
        using var parameters = new EncoderParameters(1);
        parameters.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, 90L);
        image.Save(stream, JpegEncoder, parameters);

        var frame = new GameFrame(stream.ToArray(), window, processId, bounds, sceneSize, scene);
        if (!IsCurrent(frame))
            throw new InvalidOperationException("Okno gry zmieniło się podczas zapisywania obrazu. Spróbuj ponownie.");
        return frame;
    }

    public static bool IsCurrent(GameFrame frame) =>
        GetForegroundWindow() == frame.Window &&
        GetWindowThreadProcessId(frame.Window, out uint processId) != 0 &&
        processId == frame.ProcessId &&
        IsWindowVisible(frame.Window) && !IsIconic(frame.Window) &&
        TryGetClientBounds(frame.Window, out Rectangle bounds) && bounds == frame.ClientBounds;

    internal static bool IsCurrent(GameFrame frame, RectangleF target)
    {
        if (!IsCurrent(frame))
            return false;

        try
        {
            using Bitmap bitmap = CaptureClient(frame.Window, frame.ClientBounds);
            int[] scene = SampleScene(bitmap, frame.SceneSize);
            return IsCurrent(frame) && SceneMatches(frame, scene, target);
        }
        catch (InvalidOperationException)
        {
            return false;
        }
    }

    internal static bool TryMapTarget(GameFrame frame, RectangleF target, out Rectangle bounds)
    {
        bounds = Rectangle.Empty;
        if (!float.IsFinite(target.X) || !float.IsFinite(target.Y) ||
            !float.IsFinite(target.Width) || !float.IsFinite(target.Height) ||
            target.X < 0 || target.Y < 0 || target.Width <= 0 || target.Height <= 0 ||
            target.Right > 1 || target.Bottom > 1)
            return false;

        Rectangle client = frame.ClientBounds;
        bounds = Rectangle.FromLTRB(
            client.Left + (int)Math.Floor(target.Left * client.Width),
            client.Top + (int)Math.Floor(target.Top * client.Height),
            client.Left + (int)Math.Ceiling(target.Right * client.Width),
            client.Top + (int)Math.Ceiling(target.Bottom * client.Height));
        return bounds.Width >= 4 && bounds.Height >= 4 && client.Contains(bounds);
    }

    private static bool TryGetIdentity(nint window, out uint processId)
    {
        processId = 0;
        if (window == 0 || !IsWindowVisible(window) || IsIconic(window) ||
            GetAncestor(window, RootOwner) != window ||
            GetWindowThreadProcessId(window, out processId) == 0)
            return false;

        try
        {
            using var process = Process.GetProcessById((int)processId);
            return process.ProcessName.Equals("eu4", StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or Win32Exception)
        {
            return false;
        }
    }

    private static bool TryGetClientBounds(nint window, out Rectangle bounds)
    {
        bounds = Rectangle.Empty;
        if (DwmGetWindowAttribute(window, Cloaked, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
            return false;

        // The capture API and the overlay both use physical screen pixels.
        nint oldContext = SetThreadDpiAwarenessContext(-4); // Per-monitor aware v2.
        try
        {
            if (!GetClientRect(window, out NativeRect client))
                return false;
            Point topLeft = new(client.Left, client.Top);
            Point bottomRight = new(client.Right, client.Bottom);
            if (!ClientToScreen(window, ref topLeft) || !ClientToScreen(window, ref bottomRight))
                return false;
            bounds = Rectangle.FromLTRB(topLeft.X, topLeft.Y, bottomRight.X, bottomRight.Y);
            return bounds.Width >= 64 && bounds.Height >= 64;
        }
        finally
        {
            if (oldContext != 0)
                SetThreadDpiAwarenessContext(oldContext);
        }
    }

    private static Bitmap CaptureClient(nint window, Rectangle client)
    {
        if (!OperatingSystem.IsWindowsVersionAtLeast(10, 0, 19041))
            throw new InvalidOperationException("Przechwytywanie okna gry wymaga Windows 10 w wersji 2004 lub nowszej.");

        Rectangle[] windowBounds = GetCaptureBounds(window, client);
        Bitmap bitmap;
        try
        {
            bitmap = WindowCapture.Capture(window, client, windowBounds);
        }
        catch (ExternalException error)
        {
            throw new InvalidOperationException(
                "Windows nie udostępnił obrazu gry. Ustaw tryb okienkowy lub okienkowy bez ramek i spróbuj ponownie.",
                error);
        }

        if (GetForegroundWindow() == window && TryGetClientBounds(window, out Rectangle current) && current == client)
            return bitmap;

        bitmap.Dispose();
        throw new InvalidOperationException("Okno gry zmieniło się podczas odczytu. Spróbuj ponownie.");
    }

    private static Rectangle[] GetCaptureBounds(nint window, Rectangle client)
    {
        var bounds = new List<Rectangle>(3);
        nint oldContext = SetThreadDpiAwarenessContext(-4);
        try
        {
            if (DwmGetWindowAttribute(window, ExtendedFrameBounds, out NativeRect visible,
                    Marshal.SizeOf<NativeRect>()) == 0)
                bounds.Add(visible.ToRectangle());
            if (GetWindowRect(window, out NativeRect outer))
                bounds.Add(outer.ToRectangle());
            bounds.Add(client);
        }
        finally
        {
            if (oldContext != 0)
                SetThreadDpiAwarenessContext(oldContext);
        }
        return bounds.ToArray();
    }

    private static Size Fit(Size size, int longestSide)
    {
        double scale = Math.Min(1, longestSide / (double)Math.Max(size.Width, size.Height));
        return new Size(Math.Max(1, (int)Math.Round(size.Width * scale)),
            Math.Max(1, (int)Math.Round(size.Height * scale)));
    }

    private static Bitmap Scale(Bitmap bitmap, Size size)
    {
        var result = new Bitmap(size.Width, size.Height, PixelFormat.Format32bppRgb);
        using Graphics graphics = Graphics.FromImage(result);
        graphics.InterpolationMode = InterpolationMode.HighQualityBilinear;
        graphics.PixelOffsetMode = PixelOffsetMode.HighQuality;
        graphics.DrawImage(bitmap, new Rectangle(Point.Empty, size),
            new Rectangle(Point.Empty, bitmap.Size), GraphicsUnit.Pixel);
        return result;
    }

    private static int[] SampleScene(Bitmap bitmap, Size size)
    {
        using Bitmap scaled = Scale(bitmap, size);
        var pixels = new int[size.Width * size.Height];
        BitmapData data = scaled.LockBits(new Rectangle(Point.Empty, size),
            ImageLockMode.ReadOnly, PixelFormat.Format32bppRgb);
        try
        {
            for (int y = 0; y < size.Height; y++)
                Marshal.Copy(data.Scan0 + y * data.Stride, pixels, y * size.Width, size.Width);
        }
        finally
        {
            scaled.UnlockBits(data);
        }

        int visible = pixels.Count(pixel => (pixel & 0xff) > 14 || ((pixel >> 8) & 0xff) > 14 ||
            ((pixel >> 16) & 0xff) > 14);
        if (visible < pixels.Length / 20)
            throw new InvalidOperationException("Gra zwróciła czarny obraz. Ustaw tryb okienkowy lub okienkowy bez ramek.");
        return pixels;
    }

    internal static bool SceneMatches(GameFrame frame, int[] current, RectangleF target)
    {
        int width = frame.SceneSize.Width;
        int height = frame.SceneSize.Height;
        int left = Math.Max(0, (int)Math.Floor(target.Left * width));
        int top = Math.Max(0, (int)Math.Floor(target.Top * height));
        int right = Math.Min(width, (int)Math.Ceiling(target.Right * width));
        int bottom = Math.Min(height, (int)Math.Ceiling(target.Bottom * height));
        return RegionMatches(frame.Scene, current, width, left, top, right, bottom, 0.14);
    }

    private static bool RegionMatches(int[] baseline, int[] current, int stride,
        int left, int top, int right, int bottom, double tolerance)
    {
        int allowedChanges = (int)((right - left) * (bottom - top) * tolerance);
        int changes = 0;
        for (int y = top; y < bottom; y++)
        {
            for (int x = left; x < right; x++)
            {
                int index = y * stride + x;
                if (ColorDistance(baseline[index], current[index]) > 30 && ++changes > allowedChanges)
                    return false;
            }
        }
        return true;
    }

    private static int ColorDistance(int first, int second) =>
        Math.Abs((first & 0xff) - (second & 0xff)) +
        Math.Abs(((first >> 8) & 0xff) - ((second >> 8) & 0xff)) +
        Math.Abs(((first >> 16) & 0xff) - ((second >> 16) & 0xff));

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeRect
    {
        public int Left, Top, Right, Bottom;
        public readonly Rectangle ToRectangle() => Rectangle.FromLTRB(Left, Top, Right, Bottom);
    }

    [DllImport("user32.dll")] private static extern nint GetForegroundWindow();
    [DllImport("user32.dll")] private static extern nint GetAncestor(nint window, uint flags);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(nint window, out uint processId);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(nint window);
    [DllImport("user32.dll")] private static extern bool IsIconic(nint window);
    [DllImport("user32.dll")] private static extern bool GetWindowRect(nint window, out NativeRect rect);
    [DllImport("user32.dll")] private static extern bool GetClientRect(nint window, out NativeRect rect);
    [DllImport("user32.dll")] private static extern bool ClientToScreen(nint window, ref Point point);
    [DllImport("user32.dll")] private static extern nint SetThreadDpiAwarenessContext(nint context);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(
        nint window, int attribute, out NativeRect value, int bytes);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(
        nint window, int attribute, out int value, int bytes);
}
