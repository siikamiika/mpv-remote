function evil(e)
	assert(loadstring(e))()
end

while true do
	print(mp.get_property("path"))
	pipe = io.open(mp.get_property("path")..".pipe")
	cmd = pipe:read()
	evil(cmd)
	pipe:close()
end
