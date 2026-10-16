-- Request loop for the long-lived Aseprite that core/worker.py drives.
--
-- Started as `aseprite --batch --script worker.lua`. Reads one JSON request per
-- stdin line and writes one framed JSON reply per request. Three requests:
--
--   load  {"id": 1, "load": [{"name": "lib.lua", "code": "..."}, ...]}
--         Sent once at startup. Each chunk is run with (lib, OPS); lib.lua
--         defines the helpers and registry, ops/*.lua register ops.
--   op    {"id": 2, "op": "canvas.add_layer", "args": {...}, "file": "/x.aseprite"}
--         Runs a registered op (see lib.lua for the edit/read/free kinds).
--   code  {"id": 3, "code": "<lua chunk>", "file": "/x.aseprite"}
--         Runs a chunk with the file open as app.activeSprite, in a fresh
--         environment where print() is captured. For run_lua_script.
--
--   reply "\30ASEMCP " .. {"id": 2, "ok": true, "result": {...}, "output": "..."}
--         "\30ASEMCP " .. {"id": 2, "ok": false, "error": {"code": "...", "message": "..."}}
--
-- After every request each open sprite is closed, so the next request starts
-- from what is on disk. Ends when stdin closes.

local FRAME = "\30ASEMCP "
local lib, OPS = {}, {}

local function close_all_sprites()
  local open = {}
  for _, sprite in ipairs(app.sprites) do open[#open + 1] = sprite end
  for _, sprite in ipairs(open) do sprite:close() end
end

local function as_error(err)
  if type(err) == "table" then
    return { code = tostring(err.code or "Error"), message = tostring(err.message or "") }
  end
  return { code = "LuaError", message = tostring(err) }
end

-- json.decode returns userdata objects whose numbers are all floats. Ops get
-- plain tables, with whole numbers as integers.
local function to_lua(value)
  if type(value) == "number" then
    -- Aseprite's math.tointeger truncates (1.5 -> 1) instead of failing, so
    -- only convert values that are already whole.
    if math.floor(value) == value then return math.tointeger(value) end
    return value
  end
  if type(value) ~= "userdata" then return value end
  local out = {}
  -- `#` counts an object's keys too, so tell arrays apart by their first item.
  if value[1] ~= nil then
    for i, item in ipairs(value) do out[i] = to_lua(item) end
  else
    for key, item in pairs(value) do out[key] = to_lua(item) end
  end
  return out
end

local function open(file)
  return app.open(file) or lib.fail("OpenFailed", "Aseprite could not open " .. file)
end

local function run_load(req)
  for _, chunk_spec in ipairs(req.load) do
    local chunk = assert(load(chunk_spec.code, "=" .. chunk_spec.name, "t"))
    chunk(lib, OPS)
  end
  return {}
end

local function run_op(req)
  local entry = OPS[req.op] or lib.fail("UnknownOp", "Unknown op " .. tostring(req.op))
  local args = to_lua(req.args) or {}
  if entry.kind == "free" then
    return { result = entry.fn(args) }
  end
  local sprite = open(req.file)
  local result
  if entry.kind == "edit" then
    app.transaction(function() result = entry.fn(sprite, args) end)
    sprite:saveAs(sprite.filename)
  else
    result = entry.fn(sprite, args)
  end
  return { result = result }
end

local function run_code(req)
  local lines = {}
  local env = setmetatable({
    print = function(...)
      local parts = {}
      for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
      lines[#lines + 1] = table.concat(parts, "\t")
    end,
  }, { __index = _G })
  if req.file then open(req.file) end
  local chunk, syntax_error = load(req.code, "=tool", "t", env)
  if not chunk then error(syntax_error, 0) end
  chunk()
  return { output = table.concat(lines, "\n") }
end

local function handle(req)
  if req.load then return run_load(req) end
  if req.op then return run_op(req) end
  return run_code(req)
end

io.stdout:setvbuf("line")
for line in io.lines() do
  local ok_decode, req = pcall(json.decode, line)
  local reply
  -- json.decode returns an indexable JSON object, not a plain table, so only
  -- a failed decode is rejected here.
  if not ok_decode or req == nil then
    reply = { ok = false, error = { code = "BadRequest", message = tostring(req) } }
  else
    local ok, body = pcall(handle, req)
    if ok then
      reply = body
      reply.ok = true
    else
      reply = { ok = false, error = as_error(body) }
    end
    reply.id = req.id
  end
  pcall(close_all_sprites)
  io.stdout:write(FRAME .. json.encode(reply) .. "\n")
  io.stdout:flush()
end
