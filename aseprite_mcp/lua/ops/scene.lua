-- Multi-sprite ops (tools/scene.py). These open their own files, so they are
-- `free` ops; the worker closes every sprite afterwards.
local lib = ...

-- Copies the named layers' cels from source to target, frame by frame.
-- Missing target layers are created at the top level. New target frames come
-- from newFrame(), which carries the previous frame's cels forward.
lib.free("scene.copy_layers", function(a)
  local source = app.open(a.source) or lib.fail("OpenFailed", "Source sprite not opened")
  local target = app.open(a.target) or lib.fail("OpenFailed", "Target sprite not opened")

  local found, missing = {}, {}
  for _, name in ipairs(a.names) do
    if lib.find_layer(source, name) then found[#found + 1] = name else missing[#missing + 1] = name end
  end
  if #found == 0 then
    lib.fail("NoLayersFound", "None of the requested layers exist in the source: " .. table.concat(missing, ", "))
  end

  app.transaction(function()
    if a.create_missing_frames then
      while #target.frames < #source.frames do target:newFrame() end
    end
    for _, name in ipairs(found) do
      local from = lib.find_layer(source, name)
      local to = lib.find_layer(target, name)
      if not to then
        to = target:newLayer()
        to.name = name
      end
      if a.replace then
        for _, frame in ipairs(target.frames) do
          local cel = to:cel(frame)
          if cel then target:deleteCel(cel) end
        end
      end
      for i = 1, math.min(#source.frames, #target.frames) do
        local cel = from:cel(source.frames[i])
        if cel and not to:cel(target.frames[i]) then
          target:newCel(to, target.frames[i], cel.image:clone(), cel.position)
        end
      end
    end
  end)
  target:saveAs(target.filename)
  return { missing = missing }
end)
