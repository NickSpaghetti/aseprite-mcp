-- Slice ops (tools/slices.py). Center and pivot are relative to the slice.
local lib = ...

local function find_slice(sprite, name)
  for _, slice in ipairs(sprite.slices) do
    if slice.name == name then return slice end
  end
  return nil
end

local function slice(sprite, name)
  return find_slice(sprite, name) or lib.fail("SliceNotFound", "Slice not found")
end

lib.edit("slices.create", function(sprite, a)
  if find_slice(sprite, a.name) then lib.fail("SliceExists", "Slice with that name already exists") end
  sprite:newSlice(Rectangle(a.x, a.y, a.width, a.height)).name = a.name
end)

lib.edit("slices.set_center", function(sprite, a)
  slice(sprite, a.name).center = Rectangle(a.x, a.y, a.width, a.height)
end)

lib.edit("slices.set_pivot", function(sprite, a)
  slice(sprite, a.name).pivot = Point(a.x, a.y)
end)

lib.edit("slices.delete", function(sprite, a)
  sprite:deleteSlice(slice(sprite, a.name))
end)

lib.read("slices.list", function(sprite)
  local list = {}
  for _, s in ipairs(sprite.slices) do
    local b = s.bounds
    local entry = { name = s.name, x = b.x, y = b.y, width = b.width, height = b.height }
    if s.center then
      local c = s.center
      entry.center = { x = c.x, y = c.y, width = c.width, height = c.height }
    end
    if s.pivot then entry.pivot = { x = s.pivot.x, y = s.pivot.y } end
    list[#list + 1] = entry
  end
  return { slices = list }
end)
