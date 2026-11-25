using System.ComponentModel;
using System.Diagnostics;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;

namespace Eu4Capture;

internal static class Program
{
    static int Main(string[] args)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        try
        {
            if (!OperatingSystem.IsWindowsVersionAtLeast(10, 0, 19041))
                throw new InvalidOperationException("Obraz gry wymaga systemu Windows 10 2004 lub nowszego.");
            if (args.Length != 1 || !Path.IsPathFullyQualified(args[0]) ||
                !Path.GetFileName(args[0]).Equals("eu4.exe", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Podaj ścieżkę do eu4.exe w instalacji gry.");
            if (SetThreadDpiAwarenessContext(-4) == 0)
                throw new InvalidOperationException("Windows nie potwierdził skali okna gry.");

            (int pid, nint window) = FindGame(Path.GetFullPath(args[0]));
            Rectangle client = ClientBounds(pid, window);
            var bounds = new List<Rectangle> { client };
            if (GetWindowRect(window, out Rect outer)) bounds.Add(outer.Rectangle);
            if (DwmGetWindowAttribute(window, 9, out Rect visible, Marshal.SizeOf<Rect>()) == 0)
                bounds.Insert(0, visible.Rectangle);

            using Bitmap frame = WindowCapture.Capture(window, client, bounds.ToArray());
            if (ClientBounds(pid, window) != client)
                throw new InvalidOperationException("Rozmiar lub położenie okna EU4 zmieniło się. Spróbuj ponownie.");
            using var sample = new Bitmap(frame, 32, 32);
            if (!Enumerable.Range(0, 1024).Any(i => sample.GetPixel(i % 32, i / 32).GetBrightness() > 0.03))
                throw new InvalidOperationException("EU4 zwróciło ciemną klatkę. Przywróć okno gry i spróbuj ponownie.");
            using var encoded = new MemoryStream();
            var codec = ImageCodecInfo.GetImageEncoders().First(c => c.FormatID == ImageFormat.Jpeg.Guid);
            using var options = new EncoderParameters(1);
            options.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, 90L);
            frame.Save(encoded, codec, options);
            encoded.Position = 0;
            using var output = Console.OpenStandardOutput();
            encoded.CopyTo(output);
            return 0;
        }
        catch (Exception error) when (error is InvalidOperationException or ExternalException or ArgumentException or IOException)
        {
            Console.Error.WriteLine(error is ExternalException
                ? "Windows nie udostępnił obrazu EU4. Przywróć okno gry lub wybierz tryb okienkowy bez ramek."
                : error.Message);
            return 1;
        }
    }

    private static (int, nint) FindGame(string executable)
    {
        var matches = new List<(int, nint)>();
        foreach (var process in Process.GetProcessesByName("eu4"))
        {
            using (process)
            {
                try
                {
                    if (string.Equals(process.MainModule?.FileName, executable, StringComparison.OrdinalIgnoreCase)
                        && process.MainWindowHandle != 0)
                        matches.Add((process.Id, process.MainWindowHandle));
                }
                catch (Exception error) when (error is InvalidOperationException or Win32Exception)
                {
                    // The process may have exited while the window was being located.
                }
            }
        }
        return matches.Count switch
        {
            1 => matches[0],
            0 => throw new InvalidOperationException("Brak okna EU4. Uruchom grę i poczekaj na jej okno."),
            _ => throw new InvalidOperationException("Wykryto kilka okien EU4 z tej instalacji. Pozostaw jedną grę.")
        };
    }

    private static Rectangle ClientBounds(int pid, nint window)
    {
        if (GetWindowThreadProcessId(window, out uint owner) == 0 || owner != pid || IsIconic(window)
            || !IsWindowVisible(window) || !GetClientRect(window, out Rect area) || area.Right < 1 || area.Bottom < 1)
            throw new InvalidOperationException("Okno EU4 jest niedostępne. Przywróć je i spróbuj ponownie.");
        Point origin = Point.Empty;
        if (!ClientToScreen(window, ref origin))
            throw new InvalidOperationException("Windows nie potwierdził położenia okna EU4.");
        return new Rectangle(origin.X, origin.Y, area.Right, area.Bottom);
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left, Top, Right, Bottom;
        public readonly Rectangle Rectangle => Rectangle.FromLTRB(Left, Top, Right, Bottom);
    }

    [DllImport("user32.dll")] private static extern nint SetThreadDpiAwarenessContext(nint context);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(nint window, out uint pid);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(nint window);
    [DllImport("user32.dll")] private static extern bool IsIconic(nint window);
    [DllImport("user32.dll")] private static extern bool GetClientRect(nint window, out Rect rect);
    [DllImport("user32.dll")] private static extern bool ClientToScreen(nint window, ref Point point);
    [DllImport("user32.dll")] private static extern bool GetWindowRect(nint window, out Rect rect);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(nint window, int key, out Rect rect, int size);
}
