using Moonlander.Reselect;

var failures = 0;

CheckEqual(0, TextMetrics.CountGraphemeClusters(string.Empty), "empty text");
CheckEqual(3, TextMetrics.CountGraphemeClusters("abc"), "ASCII text");
CheckEqual(3, TextMetrics.CountGraphemeClusters("a\r\nb"), "CRLF text");
CheckEqual(1, TextMetrics.CountGraphemeClusters("e\u0301"), "combining character");
CheckEqual(1, TextMetrics.CountGraphemeClusters("\U0001F469\u200D\U0001F4BB"), "ZWJ emoji");
CheckEqual(3, TextMetrics.CountGraphemeClusters("A\U0001F469\u200D\U0001F4BB\u05e9"), "mixed text");

var plan = InputPlanner.Create(300, 128);
CheckSequence(new[] { 128, 128, 44 }, plan.LeftArrowBatches, "left batches");
CheckSequence(new[] { 128, 128, 44 }, plan.ShiftRightArrowBatches, "shift-right batches");
CheckThrows<ArgumentOutOfRangeException>(() => InputPlanner.Create(0, 128), "zero count");
CheckThrows<ArgumentOutOfRangeException>(() => InputPlanner.Create(-1, 128), "negative count");

Console.WriteLine(failures == 0
    ? "All Moonlander.Reselect tests passed."
    : $"{failures} Moonlander.Reselect test(s) failed.");
return failures == 0 ? 0 : 1;

void CheckEqual<T>(T expected, T actual, string name)
{
    if (!EqualityComparer<T>.Default.Equals(expected, actual))
    {
        Console.Error.WriteLine($"FAIL {name}: expected {expected}, got {actual}");
        failures++;
    }
}

void CheckSequence<T>(IReadOnlyList<T> expected, IReadOnlyList<T> actual, string name)
{
    if (!expected.SequenceEqual(actual))
    {
        Console.Error.WriteLine($"FAIL {name}: expected [{string.Join(", ", expected)}], got [{string.Join(", ", actual)}]");
        failures++;
    }
}

void CheckThrows<TException>(Action action, string name) where TException : Exception
{
    try
    {
        action();
        Console.Error.WriteLine($"FAIL {name}: expected {typeof(TException).Name}");
        failures++;
    }
    catch (TException)
    {
    }
}
