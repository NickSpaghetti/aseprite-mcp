-- Canvas, frame and active-state ops (tools/canvas.py).
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

lib.edit("canvas.set_frame", function(sprite, a)
  app.activeFrame = lib.frame(sprite, a.frame)
end)

lib.edit("canvas.set_frame_duration", function(sprite, a)
  lib.frame(sprite, a.frame).duration = a.duration_ms / 1000.0
end)

lib.edit("canvas.set_layer", function(sprite, a)
  local target = lib.find_layer(sprite, a.name)
  if not target then
    if not a.create_if_missing then return end
    target = sprite:newLayer()
    target.name = a.name
  end
  app.activeLayer = target
end)
