using System.Diagnostics;
using System.Net.Http;
using System.Runtime.InteropServices;

namespace Atlas2;

internal sealed class CoachForm : Form
{
    private const int HotkeyId = 0x41A2;
    private const int WmHotkey = 0x0312;
    private const int TalkKey = (int)Keys.F8;
    private readonly TextBox key = new() { UseSystemPasswordChar = true, Dock = DockStyle.Fill };
    private readonly Button enable = new() { Text = "Włącz doradcę", AutoSize = true, Padding = new(12, 4, 12, 4) };
    private readonly Label status = new() { AutoSize = true, AccessibleRole = AccessibleRole.StatusBar };
    private readonly Label answer = new() { AutoSize = true };
    private readonly System.Windows.Forms.Timer watch = new() { Interval = 80 };
    private readonly HttpClient http = new(new HttpClientHandler { AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(45) };
    private readonly Voice voice = new();
    private readonly Overlay overlay = new();
    private readonly NotifyIcon notice = new() { Icon = SystemIcons.Information, Text = "Atlas EU4" };
    private LunaClient? luna;
    private CancellationTokenSource? turn;
    private GameFrame? frame;
    private long pressedAt;
    private bool recording, hotkeyRegistered, hotkeyFailed, closed, gameWasForeground;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr window, int id, uint modifiers, uint key);
    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr window, int id);
    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int key);

    internal CoachForm()
    {
        Text = "Atlas EU4 · Pierwszy wieczór z Polską";
        Font = new Font("Segoe UI", 10);
        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(560, 440);
        MinimumSize = new Size(460, 425);
        StartPosition = FormStartPosition.CenterScreen;
        var panel = new TableLayoutPanel {
            Dock = DockStyle.Fill, AutoScroll = true, ColumnCount = 1, Padding = new Padding(20), GrowStyle = TableLayoutPanelGrowStyle.AddRows
        };
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(panel);
        void Add(Control control)
        {
            control.Margin = new Padding(0, 0, 0, 10);
            panel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            panel.Controls.Add(control, 0, panel.RowCount++);
        }
        Add(new Label { Text = "Pierwszy wieczór z Polską", AutoSize = true, Font = new Font("Segoe UI", 17, FontStyle.Bold) });
        Add(new Label { Text = "Na mapie przytrzymaj F8, zapytaj „Co teraz?” i puść klawisz.", AutoSize = true });
        Add(new Label { Text = "Klucz API OpenAI", AutoSize = true });
        key.AccessibleName = "Klucz API OpenAI";
        key.Text = Environment.GetEnvironmentVariable("OPENAI_API_KEY") ?? "";
        Add(key);
        Add(new Label { Text = "Do OpenAI trafią Twoje nagranie i obraz okna gry z chwili pytania. Odpowiada głos AI.", AutoSize = true });
        Add(enable);
        var game = new LinkLabel { Text = "Uruchom Europa Universalis IV w Steam", AutoSize = true };
        game.LinkClicked += (_, _) => {
            try { Process.Start(new ProcessStartInfo("steam://rungameid/236850") { UseShellExecute = true }); }
            catch (System.ComponentModel.Win32Exception) { Report("Otwórz EU4 z biblioteki Steam."); }
        };
        Add(game);
        Add(status);
        Add(answer);
        panel.Resize += (_, _) => {
            foreach (var label in panel.Controls.OfType<Label>())
                label.MaximumSize = new Size(Math.Max(200, panel.ClientSize.Width - panel.Padding.Horizontal - 20), 0);
        };
        enable.Click += (_, _) => Toggle();
        AcceptButton = enable;
        watch.Tick += (_, _) => Poll();
    }

    private void Toggle()
    {
        if (luna is not null)
        {
            watch.Stop();
            ReleaseHotkey();
            CancelTurn();
            luna = null;
            key.Enabled = true;
            enable.Text = "Włącz doradcę";
            status.Text = "Doradca wyłączony.";
            notice.Visible = false;
            return;
        }
        if (string.IsNullOrWhiteSpace(key.Text))
        {
            status.Text = "Wpisz klucz OpenAI, aby włączyć głos i wskazówki.";
            key.Focus();
            return;
        }
        luna = new LunaClient(http, key.Text.Trim());
        key.Enabled = false;
        enable.Text = "Wyłącz doradcę";
        hotkeyFailed = false;
        status.Text = "Grając Polską, przytrzymaj F8 i zadaj pytanie.";
        notice.Visible = true;
        watch.Start();
    }

    private void ReleaseHotkey()
    {
        if (hotkeyRegistered)
            UnregisterHotKey(Handle, HotkeyId);
        hotkeyRegistered = false;
    }

    private void Poll()
    {
        if (!GameWindow.IsForeground())
        {
            ReleaseHotkey();
            hotkeyFailed = false;
            if (gameWasForeground)
            {
                bool interrupted = recording || turn is not null;
                CancelTurn();
                if (interrupted) status.Text = "Pytanie przerwane. Wróć do EU4 i przytrzymaj F8.";
            }
            gameWasForeground = false;
            return;
        }
        gameWasForeground = true;
        if (!hotkeyRegistered && !hotkeyFailed)
        {
            hotkeyRegistered = RegisterHotKey(Handle, HotkeyId, 0x4000, TalkKey);
            hotkeyFailed = !hotkeyRegistered;
            if (hotkeyFailed)
                Report("Inny program zajmuje F8. Zwolnij ten skrót i wróć do gry.");
        }
        if (recording && ((GetAsyncKeyState(TalkKey) & 0x8000) == 0 ||
                Environment.TickCount64 - pressedAt >= Voice.MaxRecordingSeconds * 1000))
            _ = FinishQuestion();
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == WmHotkey && message.WParam.ToInt32() == HotkeyId &&
            luna is not null && !recording && GameWindow.IsForeground())
            StartQuestion();
        base.WndProc(ref message);
    }

    private void StartQuestion()
    {
        CancelTurn();
        try
        {
            voice.StartRecording();
            recording = true;
            pressedAt = Environment.TickCount64;
            frame = GameWindow.Capture();
            answer.Text = "";
            status.Text = "Słucham. Puść F8, aby wysłać pytanie.";
        }
        catch (Exception e)
        {
            CancelTurn();
            Report(OperatorError(e));
        }
    }

    private async Task FinishQuestion()
    {
        var client = luna;
        var original = frame;
        recording = false;
        frame = null;
        using var request = new CancellationTokenSource();
        turn = request;
        try
        {
            byte[] wav = voice.StopRecording();
            if (client is null || original is null) return;
            if (wav.Length == 0)
            {
                Report("Nie słychać pytania. Przytrzymaj F8 podczas mówienia.");
                return;
            }
            if (!GameWindow.IsCurrent(original)) return;
            status.Text = "Rozpoznaję pytanie…";
            string question = await client.TranscribeAsync(wav, request.Token);
            request.Token.ThrowIfCancellationRequested();
            if (string.IsNullOrWhiteSpace(question))
            {
                Report("Nie udało się usłyszeć pytania. Przytrzymaj F8 i powtórz.");
                return;
            }
            if (!GameWindow.IsCurrent(original)) return;
            status.Text = "Twoje pytanie: " + question;
            var advice = await client.GuideAsync(question, original.Jpeg, request.Token);
            request.Token.ThrowIfCancellationRequested();
            answer.Text = advice.Message;
            if (!GameWindow.IsCurrent(original))
            {
                status.Text = "Wskazówka dotyczy widoku z chwili pytania.";
                return;
            }
            try { voice.Speak(advice.Message); }
            catch (Exception e) { Report(OperatorError(e), advice.Message); }
            if (advice.Target is RectangleF target && !overlay.Show(original, target))
                answer.Text = advice.Message + Environment.NewLine + "Ramka jest niedostępna dla tego widoku.";
        }
        catch (OperationCanceledException) when (request.IsCancellationRequested) { }
        catch (Exception e)
        {
            if (!closed && !request.IsCancellationRequested) Report(OperatorError(e));
        }
        finally { if (ReferenceEquals(turn, request)) turn = null; }
    }

    private static string OperatorError(Exception e) => e switch
    {
        InvalidOperationException => e.Message,
        OperationCanceledException or TimeoutException => "Upłynął czas odpowiedzi. Spróbuj ponownie.",
        HttpRequestException => "Nie można połączyć się z OpenAI. Sprawdź internet i spróbuj ponownie.",
        _ => "Nie udało się przygotować wskazówki. Wróć na mapę i spróbuj ponownie."
    };

    private void Report(string message, string? spokenText = null)
    {
        status.Text = message;
        if (!ContainsFocus && notice.Visible)
            notice.ShowBalloonTip(5000, "Atlas EU4", spokenText ?? message, ToolTipIcon.Info);
    }

    private void CancelTurn()
    {
        turn?.Cancel();
        turn = null;
        if (recording)
        {
            recording = false;
            try { voice.StopRecording(); } catch { /* Discard the interrupted clip. */ }
        }
        frame = null;
        overlay.Hide();
        voice.StopSpeaking();
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        closed = true;
        watch.Stop();
        ReleaseHotkey();
        CancelTurn();
        watch.Dispose();
        voice.Dispose();
        overlay.Dispose();
        notice.Dispose();
        http.Dispose();
        base.OnFormClosed(e);
    }
}
