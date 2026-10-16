-- Shared helpers and the op registry. Loaded once by the worker before the op
-- files; every op file receives this `lib` table.
--
-- An op is registered as one of three kinds. The kind, not the op, owns opening,
-- saving and transactions:
--
--   lib.edit(name, fn(sprite, args))  file opened; fn runs in a transaction;
--                                     the sprite is saved only if fn succeeds
--   lib.read(name, fn(sprite, args))  file opened; never saved
--   lib.free(name, fn(args))          no file opened; fn manages its own files
--
-- fn returns a table (sent back as JSON) or nothing. Failures are raised with
-- lib.fail(code, message) and reach Python as AsepriteError.

local lib, OPS = ...

function lib.edit(name, fn) OPS[name] = { kind = "edit", fn = fn } end
function lib.read(name, fn) OPS[name] = { kind = "read", fn = fn } end
function lib.free(name, fn) OPS[name] = { kind = "free", fn = fn } end

function lib.fail(code, message)
  error({ code = code, message = message }, 0)
end

-- Resolve a layer by name, searching inside groups.
--
--   1. An exact full-name match (including any "/") is tried first, breadth-
--      first, so a shallower layer wins over a deeper namesake and a layer or
--      group whose own name contains "/" is reachable directly.
--   2. Otherwise the name is read as a "group/child" path. Aseprite allows "/"
--      inside names, so segments are matched longest-prefix-first with
--      backtracking: "abc/x/y" resolves a group named "abc/x" then child "y",
--      yet a genuine "abc" -> "x" -> "y" hierarchy still resolves because a
--      dead-end longer prefix falls back to the shorter one.
function lib.find_layer(sprite, name)
  local queue = {}
  for _, layer in ipairs(sprite.layers) do queue[#queue + 1] = layer end
  local head = 1
  while head <= #queue do
    local layer = queue[head]
    head = head + 1
    if layer.name == name then return layer end
    if layer.isGroup then
      for _, child in ipairs(layer.layers) do queue[#queue + 1] = child end
    end
  end
  if not string.find(name, "/", 1, true) then return nil end
  local segs = {}
  for segment in string.gmatch(name, "[^/]+") do segs[#segs + 1] = segment end
  local function resolve(layers, i)
    for j = #segs, i, -1 do
      local candidate = table.concat(segs, "/", i, j)
      for _, layer in ipairs(layers) do
        if layer.name == candidate then
          if j == #segs then return layer end
          if layer.isGroup then
            local found = resolve(layer.layers, j + 1)
            if found then return found end
          end
        end
      end
    end
    return nil
  end
  return resolve(sprite.layers, 1)
end

function lib.layer(sprite, name)
  return lib.find_layer(sprite, name) or lib.fail("LayerNotFound", "Layer not found")
end

function lib.group(sprite, name, not_found_message)
  local group = lib.find_layer(sprite, name)
  if not group then lib.fail("GroupNotFound", not_found_message or "Group not found") end
  if not group.isGroup then lib.fail("NotAGroup", "Target is not a group") end
  return group
end

function lib.frame(sprite, index)
  return sprite.frames[index] or lib.fail("FrameOutOfRange", "Frame index out of range")
end
