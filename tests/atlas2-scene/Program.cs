using Atlas2;

var size = new Size(128, 64);
var bounds = new Rectangle(Point.Empty, size);
var pixels = Enumerable.Repeat(0x226633, size.Width * size.Height).ToArray();
var icon = new Rectangle(16, 0, 16, 8);
var target = new RectangleF(0.125f, 0, 0.125f, 0.125f);
void PaintIcon(int[] image, int color)
{
    for (int y = icon.Top; y < icon.Bottom; y++)
        Array.Fill(image, color, y * size.Width + icon.Left, icon.Width);
}
PaintIcon(pixels, 0xffcc00);
var frame = new GameFrame([], 0, 0, bounds, size, pixels);
var movedMap = Enumerable.Repeat(0x334499, pixels.Length).ToArray();
PaintIcon(movedMap, 0xffcc00);
if (!GameWindow.SceneMatches(frame, movedMap, target))
    throw new Exception("Moving the map hid a stationary treasury marker.");

var coveredIcon = (int[])pixels.Clone();
PaintIcon(coveredIcon, 0x303030);
if (GameWindow.SceneMatches(frame, coveredIcon, target))
    throw new Exception("A covered treasury marker remained visible.");
Console.WriteLine("OK: moving map, covered treasury.");
