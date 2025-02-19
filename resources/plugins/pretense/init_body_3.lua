
pm = PersistenceManager:new(savefile, gm, st, ct, pl)
pm:load()

if pm:canRestore() then
	pm:restoreZones()
	pm:restoreAIMissions()
	pm:restoreBattlefield()
	pm:restoreCsar()
	pm:restoreSquads()
else
	--initial states
	Starter.start(zones)
end

timer.scheduleFunction(function(param, time)
	pm:save()
	env.info("Mission state saved")
	return time+60
end, zones, timer.getTime()+60)


--make sure support units are present where needed
ensureSpawn = {
	['golf-farp-suport'] = zones.golf,
	['november-farp-suport'] = zones.november,
	['tango-farp-suport'] = zones.tango,
	['sierra-farp-suport'] = zones.sierra,
	['cherkessk-farp-suport'] = zones.cherkessk,
	['unal-farp-suport'] = zones.unal,
	['tyrnyauz-farp-suport'] = zones.tyrnyauz
}

for grname, zn in pairs(ensureSpawn) do
	local g = Group.getByName(grname)
	if g then g:destroy() end
end

timer.scheduleFunction(function(param, time)
	
	for grname, zn in pairs(ensureSpawn) do
		local g = Group.getByName(grname)
		if zn.side == 2 then
			if not g then
				local err, msg = pcall(mist.respawnGroup,grname,true)
				if not err then
					env.info("ERROR spawning "..grname)
					env.info(msg)
				end
			end
		else
			if g then g:destroy() end
		end
	end

	return time+30
end, {}, timer.getTime()+30)


--supply injection


