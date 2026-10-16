-- Layer management ops (tools/layers.py).
local lib = ...

lib.edit("layers.delete", function(sprite, a)
  local target = lib.layer(sprite, a.name)
  if #sprite.layers <= 1 then lib.fail("OnlyLayer", "Cannot delete the only layer") end
  sprite:deleteLayer(target)
end)

lib.edit("layers.rename", function(sprite, a)
  lib.layer(sprite, a.name).name = a.new_name
end)

lib.edit("layers.duplicate", function(sprite, a)
  local source = lib.layer(sprite, a.name)
  local parent = a.group and lib.group(sprite, a.group)
  local copy = sprite:newLayer()
  copy.name = a.new_name
  copy.opacity = source.opacity
  copy.blendMode = source.blendMode
  if parent then
    copy.parent = parent
  else
    copy.stackIndex = source.stackIndex + 1
  end
  for _, frame in ipairs(sprite.frames) do
    local cel = source:cel(frame)
    if cel then
      sprite:newCel(copy, frame, cel.image:clone(), cel.position).opacity = cel.opacity
    end
  end
end)

lib.edit("layers.reorder", function(sprite, a)
  local target = lib.layer(sprite, a.name)
  if a.position > #sprite.layers then lib.fail("PositionOutOfRange", "Position out of range") end
  target.stackIndex = a.position
end)

lib.edit("layers.set_blend_mode", function(sprite, a)
  lib.layer(sprite, a.name).blendMode = BlendMode[a.mode]
end)

lib.edit("layers.merge_down", function(sprite, a)
  local target = lib.layer(sprite, a.name)
  if target.stackIndex <= 1 then
    lib.fail("BottomLayer", "Layer is the bottom layer; nothing to merge into")
  end
  app.activeLayer = target
  app.command.MergeDownLayer()
end)

lib.edit("layers.flatten", function(sprite)
  sprite:flatten()
end)
