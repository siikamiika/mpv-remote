message = mp.get_property_osd("filename").."\n"..
          "["..mp.get_property_osd("time-pos").." -"..mp.get_property_osd("time-remaining").."] ("..mp.get_property_osd("length")..")"
mp.osd_message(message, 2)
