using System.Diagnostics;
using System.Runtime.InteropServices;
using UiTimer = System.Windows.Forms.Timer;

namespace Atlas2;

internal sealed class Overlay : IDisposable
{
    private static readonly TimeSpan Lifetime = TimeSpan.FromSeconds(3);
    private static readonly TimeSpan SceneCheckInterval = TimeSpan.FromMilliseconds(550);
    private readonly BorderWindow window = new();
    private readonly UiTimer timer = new() { Interval = 80 };
    private GameFrame? currentFrame;
    private RectangleF currentTarget;
    private Rectangle screenBounds;
    private long shownAt;
    private long lastSceneCheck;
    private Task<bool>? sceneCheck;
    private bool disposed;

    public Overlay() => timer.Tick += CheckVisibility;

    public bool Show(GameFrame frame, RectangleF target)
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        Hide();
        if (!GameWindow.TryMapTarget(frame, target, out Rectangle bounds) ||
            !GameWindow.IsCurrent(frame, target) || !IsUncovered(frame.Window, bounds))
            return false;

        // Check focus again after the frame comparison and the Z-order check.
        if (!GameWindow.IsCurrent(frame))
            return false;

        currentFrame = frame;
        currentTarget = target;
        screenBounds = bounds;
        window.Bounds = bounds;
        window.Show();
        if (!window.Visible || window.Bounds != bounds || !GameWindow.IsCurrent(frame))
        {
            Hide();
            return false;
        }
        shownAt = lastSceneCheck = Stopwatch.GetTimestamp();
        timer.Start();
        return true;
    }

    public void Hide()
    {
        timer.Stop();
        currentFrame = null;
        sceneCheck = null;
        window.Hide();
    }

    private void CheckVisibility(object? sender, EventArgs args)
    {
        if (currentFrame is not { } frame || Stopwatch.GetElapsedTime(shownAt) >= Lifetime ||
            !GameWindow.IsCurrent(frame) || !IsUncovered(frame.Window, screenBounds))
        {
            Hide();
            return;
        }

        if (sceneCheck is { IsCompleted: true } completed)
        {
            sceneCheck = null;
            if (!completed.IsCompletedSuccessfully || !completed.Result)
            {
                _ = completed.Exception;
                Hide();
                return;
            }
        }

        if (sceneCheck is null && Stopwatch.GetElapsedTime(lastSceneCheck) >= SceneCheckInterval)
        {
            lastSceneCheck = Stopwatch.GetTimestamp();
            RectangleF target = currentTarget;
            sceneCheck = Task.Run(() => CheckScene(frame, target));
        }
    }

    private static bool CheckScene(GameFrame frame, RectangleF target)
    {
        try
        {
            return GameWindow.IsCurrent(frame, target);
        }
        catch (ExternalException)
        {
            return false;
        }
    }

    private bool IsUncovered(nint game, Rectangle target)
    {
        const uint previousInZOrder = 3;
        nint ownWindow = window.IsHandleCreated ? window.Handle : 0;
        nint above = GetWindow(game, previousInZOrder);
        for (int inspected = 0; above != 0 && inspected < 512;
             inspected++, above = GetWindow(above, previousInZOrder))
        {
            if (above == ownWindow || !IsWindowVisible(above) || IsIconic(above))
                continue;
            if (DwmGetWindowAttribute(above, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
                continue;
            if (DwmGetWindowAttribute(above, 9, out NativeRect visible, Marshal.SizeOf<NativeRect>()) != 0 &&
                !GetWindowRect(above, out visible))
                continue;
            if (target.IntersectsWith(Rectangle.FromLTRB(visible.Left, visible.Top, visible.Right, visible.Bottom)))
                return false;
        }
        return above == 0;
    }

    public void Dispose()
    {
        if (disposed)
            return;
        Hide();
        disposed = true;
        timer.Dispose();
        window.Dispose();
    }

    private sealed class BorderWindow : Form
    {
        private static readonly Color ClearColor = Color.FromArgb(255, 0, 255);
        private static readonly Color HighlightColor = Color.FromArgb(255, 220, 60);

        public BorderWindow()
        {
            AutoScaleMode = AutoScaleMode.None;
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.Manual;
            ShowInTaskbar = false;
            TopMost = true;
            BackColor = ClearColor;
            TransparencyKey = ClearColor;
            DoubleBuffered = true;
        }

        protected override bool ShowWithoutActivation => true;

        protected override CreateParams CreateParams
        {
            get
            {
                const int transparent = 0x20;
                const int toolWindow = 0x80;
                const int layered = 0x80000;
                const int noActivate = 0x08000000;
                CreateParams parameters = base.CreateParams;
                parameters.ExStyle |= transparent | toolWindow | layered | noActivate;
                return parameters;
            }
        }

        protected override void OnPaint(PaintEventArgs args)
        {
            base.OnPaint(args);
            Rectangle outer = ClientRectangle;
            if (outer.Width < 4 || outer.Height < 4)
                return;

            using var highlight = new SolidBrush(HighlightColor);
            args.Graphics.FillRectangle(Brushes.Black, outer);
            outer.Inflate(-1, -1);
            args.Graphics.FillRectangle(highlight, outer);
            int stroke = Math.Min(3, (Math.Min(outer.Width, outer.Height) - 1) / 2);
            if (stroke < 1)
                return;
            outer.Inflate(-stroke, -stroke);
            args.Graphics.FillRectangle(Brushes.Black, outer);
            outer.Inflate(-1, -1);
            if (outer.Width > 0 && outer.Height > 0)
            {
                using var clear = new SolidBrush(ClearColor);
                args.Graphics.FillRectangle(clear, outer);
            }
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeRect
    {
        public int Left, Top, Right, Bottom;
    }

    [DllImport("user32.dll")] private static extern nint GetWindow(nint window, uint command);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(nint window);
    [DllImport("user32.dll")] private static extern bool IsIconic(nint window);
    [DllImport("user32.dll")] private static extern bool GetWindowRect(nint window, out NativeRect rect);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(
        nint window, int attribute, out NativeRect value, int bytes);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(
        nint window, int attribute, out int value, int bytes);
}
