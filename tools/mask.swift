import Foundation
import Vision
import CoreImage

let a = CommandLine.arguments
let inURL = URL(fileURLWithPath: a[1])
guard let ci = CIImage(contentsOf: inURL) else { fatalError("cannot load") }
let ctx = CIContext()
let cs = CGColorSpace(name: CGColorSpace.sRGB)!
let handler = VNImageRequestHandler(ciImage: ci, options: [:])

let fg = VNGenerateForegroundInstanceMaskRequest()
let person = VNGeneratePersonSegmentationRequest()
person.qualityLevel = .accurate
try handler.perform([fg, person])

if let obs = fg.results?.first {
  let buf = try obs.generateScaledMaskForImage(forInstances: obs.allInstances, from: handler)
  try ctx.writePNGRepresentation(of: CIImage(cvPixelBuffer: buf), to: URL(fileURLWithPath: a[2] + "-fg.png"), format: .RGBA8, colorSpace: cs)
  print("fg instances:", obs.allInstances.count)
} else { print("fg: none") }
if let p = person.results?.first {
  var m = CIImage(cvPixelBuffer: p.pixelBuffer)
  let sx = ci.extent.width / m.extent.width, sy = ci.extent.height / m.extent.height
  m = m.transformed(by: CGAffineTransform(scaleX: sx, y: sy))
  try ctx.writePNGRepresentation(of: m, to: URL(fileURLWithPath: a[2] + "-person.png"), format: .RGBA8, colorSpace: cs)
  print("person ok")
}
