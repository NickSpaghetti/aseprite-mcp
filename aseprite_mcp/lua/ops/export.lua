-- Export helpers and import (tools/export.py). The exports themselves run
-- Aseprite's command line from Python; these ops cover what the CLI can't.
local lib = ...

-- A tag's first and last frame numbers. The CLI's --tag silently exports every
-- frame when the tag is missing, so tools check it here first.
lib.read("export.tag_range", function(sprite, a)
  local tag = lib.find_tag(sprite, a.name) or lib.fail("TagNotFound", "Tag not found")
  return { first = tag.fromFrame.frameNumber, last = tag.toFrame.frameNumber }
end)

lib.read("export.copy", function(sprite, a)
  sprite:saveCopyAs(a.output)
end)

-- Draws an image file onto the layer (created at the top level if missing),
-- blending over what is there.
lib.edit("export.import_image", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  local image = Image { fromFile = a.path } or lib.fail("ImageLoadFailed", "Could not load image")
  local layer = lib.find_layer(sprite, a.layer)
  if not layer then
    layer = sprite:newLayer()
    layer.name = a.layer
  end
  local cel = lib.paint_cel(sprite, layer, frame, true)
  cel.image:drawImage(image, Point(a.x - cel.position.x, a.y - cel.position.y))
end)
