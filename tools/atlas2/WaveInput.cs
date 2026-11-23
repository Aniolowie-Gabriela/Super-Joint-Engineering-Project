using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace Atlas2;

internal sealed class WaveInput(int maxSeconds) : IDisposable
{
    private const int SampleRate = 16_000;
    private const ushort Channels = 1;
    private const ushort BitsPerSample = 16;
    private const ushort BlockAlign = Channels * BitsPerSample / 8;
    private const int BytesPerSecond = SampleRate * BlockAlign;
    private static readonly uint HeaderSize = (uint)Marshal.SizeOf<WaveHeader>();

    private readonly int bufferSize = maxSeconds * BytesPerSecond;
    private IntPtr handle;
    private IntPtr header;
    private IntPtr data;
    private bool prepared;
    private bool recording;

    public void Start()
    {
        if (recording)
            throw new InvalidOperationException("Nagrywanie już trwa.");

        Dispose();
        if (handle != IntPtr.Zero)
            throw new InvalidOperationException("Nie udało się zwolnić mikrofonu. Uruchom ponownie Atlas.");

        var format = new WaveFormat
        {
            FormatTag = 1,
            Channels = Channels,
            SamplesPerSecond = SampleRate,
            AverageBytesPerSecond = BytesPerSecond,
            BlockAlign = BlockAlign,
            BitsPerSample = BitsPerSample
        };
        const string failure = "Nie udało się uruchomić mikrofonu";
        try
        {
            // A single bounded buffer avoids driver callbacks and stops collecting when full.
            Check(waveInOpen(out IntPtr input, uint.MaxValue, ref format, IntPtr.Zero, IntPtr.Zero, 0), failure);
            handle = input;
            data = Marshal.AllocHGlobal(bufferSize);
            header = Marshal.AllocHGlobal((int)HeaderSize);
            Marshal.StructureToPtr(new WaveHeader
            {
                Data = data,
                BufferLength = (uint)bufferSize
            }, header, false);

            Check(waveInPrepareHeader(handle, header, HeaderSize), failure);
            prepared = true;
            Check(waveInAddBuffer(handle, header, HeaderSize), failure);
            Check(waveInStart(handle), failure);
            recording = true;
        }
        catch
        {
            Dispose();
            throw;
        }
    }

    public byte[] Stop()
    {
        if (!recording)
            throw new InvalidOperationException("Nagrywanie jeszcze się nie rozpoczęło.");

        try
        {
            Check(waveInStop(handle), "Nie udało się zakończyć nagrania");
            uint recorded = Marshal.PtrToStructure<WaveHeader>(header).BytesRecorded;
            int length = (int)Math.Min(recorded, (uint)bufferSize);
            length -= length % BlockAlign;
            if (length == 0)
                return [];

            var pcm = new byte[length];
            Marshal.Copy(data, pcm, 0, length);
            return EncodeWav(pcm);
        }
        finally
        {
            Dispose();
        }
    }

    internal static byte[] EncodeWav(ReadOnlySpan<byte> pcm)
    {
        using var output = new MemoryStream(44 + pcm.Length);
        using var writer = new BinaryWriter(output);
        writer.Write("RIFF"u8);
        writer.Write(36 + pcm.Length);
        writer.Write("WAVEfmt "u8);
        writer.Write(16);
        writer.Write((ushort)1);
        writer.Write(Channels);
        writer.Write(SampleRate);
        writer.Write(BytesPerSecond);
        writer.Write(BlockAlign);
        writer.Write(BitsPerSample);
        writer.Write("data"u8);
        writer.Write(pcm.Length);
        writer.Write(pcm);
        return output.ToArray();
    }

    public void Dispose()
    {
        recording = false;
        if (handle != IntPtr.Zero)
        {
            _ = waveInReset(handle);
            if (prepared && waveInUnprepareHeader(handle, header, HeaderSize) == 0)
                prepared = false;

            if (waveInClose(handle) == 0)
            {
                handle = IntPtr.Zero;
                prepared = false;
            }
        }

        // Keep the allocation alive if a driver still owns the header after a failed close.
        if (prepared)
            return;

        Marshal.FreeHGlobal(header);
        Marshal.FreeHGlobal(data);
        header = IntPtr.Zero;
        data = IntPtr.Zero;
    }

    private static void Check(uint result, string message)
    {
        if (result == 0)
            return;

        var description = new StringBuilder(256);
        if (waveInGetErrorText(result, description, (uint)description.Capacity) != 0)
            throw new InvalidOperationException($"{message} (kod {result}).");
        throw new InvalidOperationException($"{message}. {description}");
    }

    [StructLayout(LayoutKind.Sequential, Pack = 2)]
    private struct WaveFormat
    {
        public ushort FormatTag;
        public ushort Channels;
        public uint SamplesPerSecond;
        public uint AverageBytesPerSecond;
        public ushort BlockAlign;
        public ushort BitsPerSample;
        public ushort ExtraSize;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct WaveHeader
    {
        public IntPtr Data;
        public uint BufferLength;
        public uint BytesRecorded;
        public UIntPtr User;
        public uint Flags;
        public uint Loops;
        public IntPtr Next;
        public UIntPtr Reserved;
    }

    [DllImport("winmm.dll")]
    private static extern uint waveInOpen(out IntPtr handle, uint device, ref WaveFormat format,
        IntPtr callback, IntPtr instance, uint flags);

    [DllImport("winmm.dll")]
    private static extern uint waveInPrepareHeader(IntPtr handle, IntPtr header, uint size);

    [DllImport("winmm.dll")]
    private static extern uint waveInAddBuffer(IntPtr handle, IntPtr header, uint size);

    [DllImport("winmm.dll")]
    private static extern uint waveInStart(IntPtr handle);

    [DllImport("winmm.dll")]
    private static extern uint waveInStop(IntPtr handle);

    [DllImport("winmm.dll")]
    private static extern uint waveInReset(IntPtr handle);

    [DllImport("winmm.dll")]
    private static extern uint waveInUnprepareHeader(IntPtr handle, IntPtr header, uint size);

    [DllImport("winmm.dll")]
    private static extern uint waveInClose(IntPtr handle);

    [DllImport("winmm.dll", CharSet = CharSet.Unicode)]
    private static extern uint waveInGetErrorText(uint result, StringBuilder text, uint size);
}
