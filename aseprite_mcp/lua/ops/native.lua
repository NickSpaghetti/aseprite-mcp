-- Wrappers for Aseprite's own filters (tools/native_fx.py).
--
-- app.command.* filters act on the active layer, frame and selection, not on
-- arguments, so each op activates its target first. With no `layer` the
-- target is lib.default_target's layer (the sprite's only layer).
-- `region` = [x, y, w, h] limits the filter to that rectangle through a
-- temporary selection.
local lib = ...

local function on_target(sprite, a, run)
  app.activeFrame = lib.frame(sprite, a.frame)
  app.activeLayer = a.layer and lib.layer(sprite, a.layer) or lib.default_target(sprite)
  if a.region then
    local r = a.region
    sprite.selection = Selection(Rectangle(r[1], r[2], r[3], r[4]))
  end
  run()
  if a.region then sprite.selection:deselect() end
end

lib.edit("native.outline", function(sprite, a)
  on_target(sprite, a, function()
    app.command.Outline { ui = false, color = lib.color(a.color), place = a.place, matrix = a.matrix }
  end)
end)

lib.edit("native.hue_saturation", function(sprite, a)
  on_target(sprite, a, function()
    app.command.HueSaturation { ui = false, hue = a.hue, saturation = a.saturation,
                                lightness = a.lightness, alpha = 0 }
  end)
end)

lib.edit("native.brightness_contrast", function(sprite, a)
  on_target(sprite, a, function()
    app.command.BrightnessContrast { ui = false, brightness = a.brightness, contrast = a.contrast }
  end)
end)

lib.edit("native.invert", function(sprite, a)
  on_target(sprite, a, function() app.command.InvertColor { ui = false } end)
end)

lib.edit("native.convolution", function(sprite, a)
  on_target(sprite, a, function()
    app.command.ConvolutionMatrix { ui = false, fromResource = a.matrix }
  end)
end)

-- Rebuilds the sprite palette from its pixels; returns the new colours.
lib.edit("native.extract_palette", function(sprite, a)
  app.command.ColorQuantization { ui = false, maxColors = a.max_colors, withAlpha = a.with_alpha }
  local palette, colors = sprite.palettes[1], {}
  for i = 0, #palette - 1 do
    local c = palette:getColor(i)
    colors[#colors + 1] = string.format("#%02X%02X%02X", c.red, c.green, c.blue)
  end
  return { colors = colors }
end)
