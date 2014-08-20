function evil(e)
    assert(loadstring(e))()
end

socket = require("socket")
udp = socket.udp()
udp:setsockname("localhost", 9876)

while true do
    cmd = assert(udp:receive())
    evil(cmd)
end
