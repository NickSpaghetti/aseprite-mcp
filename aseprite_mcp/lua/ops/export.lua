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

-- ── exports ──────────────────────────────────────────────────────────
--
-- Each of these reproduces the command-line export the tool used before,
-- checked file for file and pixel for pixel (redesign/test/probe/export_parity*.py).
-- They are read ops: the sprite is never saved, so the in-memory resize used
-- for sheet scaling is thrown away.

-- --save-as: a multi-frame sprite saved to a still format writes numbered files.
lib.read("export.sprite", function(sprite, a)
  sprite:saveCopyAs(a.output)
end)

-- --frame-range n,n --scale s --save-as, rendered directly: SaveFileCopyAs
-- ignores fromFrame/toFrame when run inside the worker and always writes
-- frame 1 (redesign/test/results/probe-frame-debug.log).
lib.read("export.frame", function(sprite, a)
  local index = lib.frame(sprite, a.frame).frameNumber
  lib.scale_image(lib.composite(sprite, index), a.scale):saveAs(a.output)
end)

-- --tag --scale --save-as
lib.read("export.tag", function(sprite, a)
  if not lib.find_tag(sprite, a.tag) then lib.fail("TagNotFound", "Tag not found") end
  app.command.SaveFileCopyAs { ui = false, filename = a.output, tag = a.tag, scale = a.scale }
end)

local SHEET_TYPES = {
  horizontal = SpriteSheetType.HORIZONTAL, vertical = SpriteSheetType.VERTICAL, rows = SpriteSheetType.ROWS,
  columns = SpriteSheetType.COLUMNS, packed = SpriteSheetType.PACKED,
}
local DATA_FORMATS = { ["json-array"] = SpriteSheetDataFormat.JSON_ARRAY, ["json-hash"] = SpriteSheetDataFormat.JSON_HASH }

-- --sheet with --sheet-type, --scale, --shape-padding, --data/--format/--list-tags
-- and a tag's frame range. Frame names follow the CLI: numbered only when more
-- than one frame is exported.
lib.read("export.sheet", function(sprite, a)
  local exported = #sprite.frames
  if a.tag then
    local tag = lib.find_tag(sprite, a.tag) or lib.fail("TagNotFound", "Tag not found")
    exported = tag.toFrame.frameNumber - tag.fromFrame.frameNumber + 1
  end
  if a.scale > 1 then sprite:resize(sprite.width * a.scale, sprite.height * a.scale) end
  -- Only pass what was asked for, exactly as the parity probes did.
  local params = {
    ui = false, askOverwrite = false, type = SHEET_TYPES[a.sheet_type], textureFilename = a.output,
    shapePadding = a.padding, listTags = a.list_tags, listLayers = false,
    filenameFormat = exported > 1 and "{title} {frame}.{extension}" or "{title}.{extension}",
  }
  if a.data then
    params.dataFilename = a.data
    params.dataFormat = DATA_FORMATS[a.data_format]
  end
  if a.tag then params.tag = a.tag end
  app.command.ExportSpriteSheet(params)
end)

-- --split-layers --save-as dir/{layer}.png: one PNG per layer (groups
-- composited) per frame, numbered only when the sprite has several frames.
-- Hidden layers, and layers inside hidden groups, are skipped unless
-- `include_hidden`. Each layer is rendered with only itself, its parent groups
-- and (for a group) its children visible.
lib.read("export.layers", function(sprite, a)
  local layers, visible = {}, {}
  local function walk(list)
    for _, layer in ipairs(list) do
      layers[#layers + 1] = layer
      visible[#layers] = layer.isVisible
      if layer.isGroup then walk(layer.layers) end
    end
  end
  walk(sprite.layers)

  local function index_of(layer)
    for i, l in ipairs(layers) do if l == layer then return i end end
  end
  local function shown(layer)
    while layer and layer ~= sprite do
      if not visible[index_of(layer)] then return false end
      layer = layer.parent
    end
    return true
  end
  local function contains(outer, layer)
    while layer and layer ~= sprite do
      if layer == outer then return true end
      layer = layer.parent
    end
    return false
  end

  local written = {}
  for _, target in ipairs(layers) do
    if a.include_hidden or shown(target) then
      for _, layer in ipairs(layers) do
        layer.isVisible = contains(target, layer) or contains(layer, target)
      end
      for n = 1, #sprite.frames do
        local image = Image(sprite.width, sprite.height, ColorMode.RGB)
        image:drawSprite(sprite, n)
        local name = target.name .. (#sprite.frames > 1 and tostring(n) or "") .. ".png"
        image:saveAs(a.directory .. "/" .. name)
        written[#written + 1] = name
      end
    end
  end
  return { written = written }
end)
