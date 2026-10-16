-- Request loop for the long-lived Aseprite that core/worker.py drives.
--
-- Started as `aseprite --batch --script worker.lua`. Reads one JSON request per
-- stdin line and writes one framed JSON reply per request:
--
--   request  {"id": 1, "code": "<lua chunk>", "file": "/path.aseprite"}   ("file" optional)
--   reply    "\30ASEMCP " .. {"id": 1, "ok": true, "output": "..."}
--            "\30ASEMCP " .. {"id": 1, "ok": false, "error": {"code": "...", "message": "..."}}
--
-- Each request opens its file, runs its chunk in a fresh environment (so globals
-- do not carry over and print() is captured), then closes every open sprite, so
-- the next request starts from what is on disk. Ends when stdin closes.

local FRAME = "\30ASEMCP "

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

local function handle(req)
  local lines = {}
  local env = setmetatable({
    print = function(...)
      local parts = {}
      for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
      lines[#lines + 1] = table.concat(parts, "\t")
    end,
  }, { __index = _G })

  if req.file then
    local sprite = app.open(req.file)
    if not sprite then
      return false, { code = "OpenFailed", message = "Aseprite could not open " .. req.file }
    end
  end

  local chunk, syntax_error = load(req.code, "=tool", "t", env)
  if not chunk then return false, as_error(syntax_error) end
  local ok, err = pcall(chunk)
  if not ok then return false, as_error(err) end
  return true, table.concat(lines, "\n")
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
    local ok_run, ok, result = pcall(handle, req)
    if not ok_run then ok, result = false, as_error(ok) end
    reply = { id = req.id, ok = ok }
    if ok then reply.output = result else reply.error = result end
  end
  pcall(close_all_sprites)
  io.stdout:write(FRAME .. json.encode(reply) .. "\n")
  io.stdout:flush()
end
