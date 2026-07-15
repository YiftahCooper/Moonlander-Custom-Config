using System.Text;

namespace Moonlander.Reselect;

internal static class Program
{
    private const int Success = 0;
    private const int InvalidInput = 2;
    private const int IncompleteSendInput = 3;

    public static int Main(string[] args)
    {
        var dryRun = args.Length == 1 && args[0] == "--dry-run";
        if (args.Length > 1 || (args.Length == 1 && !dryRun))
        {
            Console.Error.WriteLine("Usage: Moonlander.Reselect [--dry-run]");
            return InvalidInput;
        }

        string text;
        try
        {
            using var reader = new StreamReader(
                Console.OpenStandardInput(),
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true),
                detectEncodingFromByteOrderMarks: true);
            text = reader.ReadToEnd();
        }
        catch (DecoderFallbackException)
        {
            Console.Error.WriteLine("Standard input is not valid UTF-8.");
            return InvalidInput;
        }

        if (text.Length == 0)
        {
            Console.Error.WriteLine("Standard input must contain transformed UTF-8 text.");
            return InvalidInput;
        }

        var graphemeCount = TextMetrics.CountGraphemeClusters(text);
        if (graphemeCount == 0)
        {
            return InvalidInput;
        }

        if (dryRun)
        {
            Console.WriteLine(graphemeCount);
            return Success;
        }

        return Reselection.Execute(graphemeCount, new WinInputSender())
            ? Success
            : IncompleteSendInput;
    }
}
