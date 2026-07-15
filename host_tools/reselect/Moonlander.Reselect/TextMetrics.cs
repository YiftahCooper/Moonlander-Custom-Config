using System.Globalization;

namespace Moonlander.Reselect;

internal static class TextMetrics
{
    public static int CountGraphemeClusters(string text) =>
        StringInfo.ParseCombiningCharacters(text).Length;
}
