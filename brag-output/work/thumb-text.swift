// Renders the text layer for the Devpost logo GIF (transparent PNG, 1440x960 = 2x of 720x480).
//   swift brag-output/work/thumb-text.swift <geist.woff2> <out.png>
import AppKit
import CoreText

let args = CommandLine.arguments
let fontURL = URL(fileURLWithPath: args[1]) as CFURL
let out = URL(fileURLWithPath: args[2])
var family = "Helvetica Neue"
if let descs = CTFontManagerCreateFontDescriptorsFromURL(fontURL) as? [CTFontDescriptor], let d = descs.first {
  CTFontManagerRegisterFontsForURL(fontURL, .process, nil)
  family = (CTFontDescriptorCopyAttribute(d, kCTFontFamilyNameAttribute) as? String) ?? family
}
FileHandle.standardError.write("font family: \(family)\n".data(using: .utf8)!)

func font(_ size: CGFloat, _ weight: NSFont.Weight) -> NSFont {
  let d = NSFontDescriptor(fontAttributes: [.family: family, .traits: [NSFontDescriptor.TraitKey.weight: weight]])
  return NSFont(descriptor: d, size: size) ?? NSFont.systemFont(ofSize: size, weight: weight)
}
func color(_ hex: Int, _ a: CGFloat = 1) -> NSColor {
  NSColor(srgbRed: CGFloat((hex >> 16) & 255) / 255, green: CGFloat((hex >> 8) & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: a)
}

let W = 1440, H = 960
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H, bitsPerSample: 8, samplesPerPixel: 4,
                           hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSColor.clear.set(); NSRect(x: 0, y: 0, width: W, height: H).fill()

// y is measured from the top of the image; AppKit draws from the bottom, so flip.
func draw(_ s: String, x: CGFloat, top: CGFloat, size: CGFloat, weight: NSFont.Weight, hex: Int, kern: CGFloat = 0) {
  let attr: [NSAttributedString.Key: Any] = [.font: font(size, weight), .foregroundColor: color(hex), .kern: kern]
  let a = NSAttributedString(string: s, attributes: attr)
  let h = a.size().height
  a.draw(at: NSPoint(x: x, y: CGFloat(H) - top - h))
}

let x: CGFloat = 760
draw("HACKPRINCETON FALL '26", x: x, top: 340, size: 26, weight: .semibold, hex: 0x7C5CFF, kern: 3)
draw("Stellaris", x: x - 6, top: 380, size: 150, weight: .semibold, hex: 0x15151A, kern: -5)
draw("From question to discovery.", x: x, top: 570, size: 46, weight: .regular, hex: 0x55555F)

NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: out)
print("saved \(out.path)")
