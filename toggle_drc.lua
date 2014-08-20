af_list = mp.get_property_native("af")
local applied = false
for i, af in pairs(af_list) do
    if af["name"] == "drc" then
        applied = i
        break
    end
end

if applied then
    table.remove(af_list, applied)
    mp.osd_message("DRC removed")
else
    af_list[#af_list+1] = {name = "drc", params = {method = "1", target = "0.25"}}
    mp.osd_message("DRC applied")
end

mp.set_property_native("af", af_list)
