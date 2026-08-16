using System;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace ClipboardImageToIco
{
    static class Program
    {
        static readonly int[] StandardSizes = new int[] { 256, 128, 64, 48, 32, 24, 16 };

        [STAThread]
        static void Main()
        {
            string targetPath = null;

            if (Clipboard.ContainsFileDropList())
            {
                StringCollection files = Clipboard.GetFileDropList();
                if (files.Count > 0) targetPath = files[0];
            }
            else if (Clipboard.ContainsText())
            {
                string text = Clipboard.GetText().Trim().Trim('"');
                if (File.Exists(text)) targetPath = text;
            }

            if (string.IsNullOrEmpty(targetPath) || !File.Exists(targetPath)) return;

            string outputPath = Path.ChangeExtension(targetPath, ".ico");

            try
            {
                ConvertImageToIco(targetPath, outputPath);
            }
            catch { }
        }

        static void ConvertImageToIco(string inputPath, string outputPath)
        {
            using (Bitmap src = new Bitmap(inputPath))
            {
                List<byte[]> iconDataStreams = new List<byte[]>();
                List<int> sizes = new List<int>();

                foreach (int size in StandardSizes)
                {
                    using (Bitmap resized = CreateSquareIconFrame(src, size))
                    {
                        if (size == 256)
                        {
                            using (MemoryStream ms = new MemoryStream())
                            {
                                resized.Save(ms, ImageFormat.Png);
                                iconDataStreams.Add(ms.ToArray());
                                sizes.Add(size);
                            }
                        }
                        else
                        {
                            byte[] dibData = CreateDibIconFrame(resized);
                            iconDataStreams.Add(dibData);
                            sizes.Add(size);
                        }
                    }
                }

                using (FileStream fs = new FileStream(outputPath, FileMode.Create, FileAccess.Write))
                using (BinaryWriter bw = new BinaryWriter(fs))
                {
                    bw.Write((short)0); // Reserved
                    bw.Write((short)1); // Type ICO
                    bw.Write((short)iconDataStreams.Count);

                    int offset = 6 + (16 * iconDataStreams.Count);

                    for (int i = 0; i < iconDataStreams.Count; i++)
                    {
                        byte w = sizes[i] >= 256 ? (byte)0 : (byte)sizes[i];
                        byte h = sizes[i] >= 256 ? (byte)0 : (byte)sizes[i];

                        bw.Write(w);
                        bw.Write(h);
                        bw.Write((byte)0); // Color count
                        bw.Write((byte)0); // Reserved
                        bw.Write((short)1); // Color planes
                        bw.Write((short)32); // Bits per pixel
                        bw.Write((int)iconDataStreams[i].Length);
                        bw.Write(offset);

                        offset += iconDataStreams[i].Length;
                    }

                    foreach (byte[] stream in iconDataStreams)
                    {
                        bw.Write(stream);
                    }
                }
            }
        }

        static byte[] CreateDibIconFrame(Bitmap bitmap)
        {
            int width = bitmap.Width;
            int height = bitmap.Height;
            int maskRowSize = ((width + 31) / 32) * 4;
            int maskSize = maskRowSize * height;
            int imageSize = width * height * 4;
            int headerSize = 40;

            byte[] buffer = new byte[headerSize + imageSize + maskSize];

            using (MemoryStream ms = new MemoryStream(buffer))
            using (BinaryWriter bw = new BinaryWriter(ms))
            {
                // BITMAPINFOHEADER
                bw.Write(headerSize);
                bw.Write(width);
                bw.Write(height * 2); // Double height for XOR + AND masks
                bw.Write((short)1);   // Planes
                bw.Write((short)32);  // 32-bit BGRA
                bw.Write(0);          // BI_RGB (no compression)
                bw.Write(imageSize + maskSize);
                bw.Write(0);
                bw.Write(0);
                bw.Write(0);
                bw.Write(0);

                // Pixel data: Bottom-up 32bpp BGRA
                BitmapData bmpData = bitmap.LockBits(new Rectangle(0, 0, width, height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                byte[] row = new byte[width * 4];

                for (int y = height - 1; y >= 0; y--)
                {
                    IntPtr srcPtr = new IntPtr(bmpData.Scan0.ToInt64() + (y * bmpData.Stride));
                    Marshal.Copy(srcPtr, row, 0, row.Length);
                    bw.Write(row);
                }

                bitmap.UnlockBits(bmpData);

                // 1-bit AND Mask (all transparent to use 32-bit alpha channel)
                byte[] andMask = new byte[maskSize];
                bw.Write(andMask);
            }

            return buffer;
        }

        static Bitmap CreateSquareIconFrame(Bitmap original, int targetSize)
        {
            Bitmap canvas = new Bitmap(targetSize, targetSize, PixelFormat.Format32bppArgb);
            canvas.SetResolution(original.HorizontalResolution, original.VerticalResolution);

            using (Graphics g = Graphics.FromImage(canvas))
            {
                g.Clear(Color.Transparent);
                g.CompositingMode = CompositingMode.SourceOver;
                g.CompositingQuality = CompositingQuality.HighQuality;
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.SmoothingMode = SmoothingMode.HighQuality;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;

                float scale = Math.Min((float)targetSize / original.Width, (float)targetSize / original.Height);
                int scaledWidth = (int)(original.Width * scale);
                int scaledHeight = (int)(original.Height * scale);
                int posX = (targetSize - scaledWidth) / 2;
                int posY = (targetSize - scaledHeight) / 2;

                using (ImageAttributes wrapMode = new ImageAttributes())
                {
                    wrapMode.SetWrapMode(WrapMode.TileFlipXY);
                    g.DrawImage(original, new Rectangle(posX, posY, scaledWidth, scaledHeight), 0, 0, original.Width, original.Height, GraphicsUnit.Pixel, wrapMode);
                }
            }

            return canvas;
        }
    }
}