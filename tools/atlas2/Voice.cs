using System;
using System.Runtime.InteropServices;

namespace Atlas2;

internal sealed class Voice : IDisposable
{
    public const int MaxRecordingSeconds = 20;

    private const int SpeakAsync = 1;
    private const int PurgeBeforeSpeak = 2;
    private const int ReadAsText = 16;
    private readonly WaveInput microphone = new(MaxRecordingSeconds);
    private object? speaker;
    private bool disposed;

    public void StartRecording()
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        StopSpeaking();
        microphone.Start();
    }

    public byte[] StopRecording()
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        return microphone.Stop();
    }

    public void Speak(string text)
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        if (string.IsNullOrWhiteSpace(text))
            return;

        try
        {
            dynamic voice = speaker ??= CreatePolishSpeaker();
            voice.Speak(text, SpeakAsync | PurgeBeforeSpeak | ReadAsText);
        }
        catch (COMException error)
        {
            ReleaseSpeaker();
            throw new InvalidOperationException(
                "Nie udało się odczytać odpowiedzi głosem Windows. Możesz przeczytać ją na ekranie.", error);
        }
    }

    public void StopSpeaking()
    {
        if (speaker is not { } current)
            return;

        try
        {
            ((dynamic)current).Speak("", SpeakAsync | PurgeBeforeSpeak | ReadAsText);
        }
        catch (COMException)
        {
            ReleaseSpeaker();
        }
    }

    public void Dispose()
    {
        if (disposed)
            return;

        disposed = true;
        microphone.Dispose();
        StopSpeaking();
        ReleaseSpeaker();
    }

    private static object CreatePolishSpeaker()
    {
        var type = Type.GetTypeFromProgID("SAPI.SpVoice");
        if (type is null)
            throw new InvalidOperationException("Synteza mowy Windows jest niedostępna.");

        object voice = Activator.CreateInstance(type)!;
        object? voices = null;
        object? token = null;
        try
        {
            dynamic sapi = voice;
            // The SAPI language attribute uses hexadecimal Windows locale IDs.
            voices = sapi.GetVoices("Language=415", "");
            dynamic tokens = voices!;
            if (tokens.Count == 0)
                throw new InvalidOperationException(
                    "Dodaj polski głos w ustawieniach Windows (Czas i język → Mowa).");

            token = tokens.Item(0);
            sapi.Voice = token;
            return voice;
        }
        catch
        {
            Marshal.ReleaseComObject(voice);
            throw;
        }
        finally
        {
            if (token is not null)
                Marshal.ReleaseComObject(token);
            if (voices is not null)
                Marshal.ReleaseComObject(voices);
        }
    }

    private void ReleaseSpeaker()
    {
        if (speaker is not { } current)
            return;

        speaker = null;
        Marshal.ReleaseComObject(current);
    }
}
