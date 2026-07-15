using System.Runtime.InteropServices;

namespace Moonlander.Reselect;

internal sealed class WinInputSender
{
    private const uint InputKeyboard = 1;
    private const uint KeyEventExtendedKey = 0x0001;
    private const uint KeyEventKeyUp = 0x0002;
    private const ushort VirtualKeyShift = 0x10;
    private const ushort VirtualKeyLeft = 0x25;
    private const ushort VirtualKeyRight = 0x27;

    public bool SendArrowBatch(bool moveRight, int count)
    {
        var inputs = new Input[count * 2];
        var virtualKey = moveRight ? VirtualKeyRight : VirtualKeyLeft;
        for (var index = 0; index < count; index++)
        {
            inputs[index * 2] = CreateKeyInput(virtualKey, KeyEventExtendedKey);
            inputs[index * 2 + 1] = CreateKeyInput(
                virtualKey,
                KeyEventExtendedKey | KeyEventKeyUp);
        }

        return Send(inputs);
    }

    public bool SendShift(bool pressed)
    {
        var flags = pressed ? 0u : KeyEventKeyUp;
        return Send(new[] { CreateKeyInput(VirtualKeyShift, flags) });
    }

    private static bool Send(Input[] inputs) =>
        SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>()) == inputs.Length;

    private static Input CreateKeyInput(ushort virtualKey, uint flags) => new()
    {
        Type = InputKeyboard,
        Union = new InputUnion
        {
            Keyboard = new KeyboardInput
            {
                VirtualKey = virtualKey,
                Flags = flags,
            },
        },
    };

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint inputCount, Input[] inputs, int inputSize);

    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        public uint Type;
        public InputUnion Union;
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)]
        public KeyboardInput Keyboard;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public nuint ExtraInfo;
    }
}
