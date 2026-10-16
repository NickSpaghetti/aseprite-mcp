-- Canvas, layer and frame ops (tools/canvas.py).
local lib = ...

lib.free("canvas.create", function(a)
  local sprite = Sprite(a.width, a.height)
  sprite:saveAs(a.filename)
end)

lib.edit("canvas.add_layer", function(sprite, a)
  local parent = a.group and lib.group(sprite, a.group)
  local layer = sprite:newLayer()
  layer.name = a.name
  if parent then layer.parent = parent end
end)

lib.edit("canvas.add_group", function(sprite, a)
  local parent = a.parent and lib.group(sprite, a.parent, "Parent group not found")
  local group = sprite:newGroup()
  group.name = a.name
  if parent then group.parent = parent end
end)

lib.edit("canvas.add_frame", function(sprite)
  sprite:newFrame()
end)

-- Aseprite keeps no active frame or layer between requests, so set_frame and
-- set_layer only check; creating a missing layer goes through add_layer.
lib.read("canvas.check_frame", function(sprite, a)
  lib.frame(sprite, a.frame)
end)

lib.edit("canvas.set_frame_duration", function(sprite, a)
  lib.frame(sprite, a.frame).duration = a.duration_ms / 1000.0
end)

lib.read("canvas.layer_exists", function(sprite, a)
  return { exists = lib.find_layer(sprite, a.name) ~= nil }
end)
