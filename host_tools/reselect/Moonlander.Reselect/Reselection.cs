namespace Moonlander.Reselect;

internal static class Reselection
{
    private const int BatchSize = 128;

    public static bool Execute(int graphemeCount, WinInputSender sender)
    {
        var plan = InputPlanner.Create(graphemeCount, BatchSize);
        foreach (var batch in plan.LeftArrowBatches)
        {
            if (!sender.SendArrowBatch(moveRight: false, batch))
            {
                return false;
            }
        }

        Thread.Sleep(10);
        if (!sender.SendShift(pressed: true))
        {
            return false;
        }

        var complete = true;
        try
        {
            foreach (var batch in plan.ShiftRightArrowBatches)
            {
                if (!sender.SendArrowBatch(moveRight: true, batch))
                {
                    complete = false;
                    break;
                }
            }
        }
        finally
        {
            complete = sender.SendShift(pressed: false) && complete;
        }

        return complete;
    }
}
