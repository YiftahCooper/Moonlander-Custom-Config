namespace Moonlander.Reselect;

internal sealed record InputPlan(
    IReadOnlyList<int> LeftArrowBatches,
    IReadOnlyList<int> ShiftRightArrowBatches);

internal static class InputPlanner
{
    public static InputPlan Create(int graphemeCount, int batchSize)
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(graphemeCount);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(batchSize);

        var batches = new List<int>();
        for (var remaining = graphemeCount; remaining > 0; remaining -= batchSize)
        {
            batches.Add(Math.Min(remaining, batchSize));
        }

        return new InputPlan(batches, batches.ToArray());
    }
}
