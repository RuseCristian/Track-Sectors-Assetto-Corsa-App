# Track-Sectors-Assetto-Corsa-App

Ever wanted to improve your time on a track, but never managed to pinpoint where you were fast and where you were slow? This app solves the problem. It let's you create N sectors on a track and record your times.

[RACEDEPARTMENT LINK](https://www.racedepartment.com/downloads/track-sectors-divide-the-track-in-sections.43904/)

Video Demonstration :

[![Video Demonstration of The App](thumbnail.png)]([https://www.youtube.com/watch?v=9x-IG0ybvn8](https://www.youtube.com/watch?v=c0fWVsOLjeA))


## How To Use - Please READ:

Select how many sectors you want to use, then simply press the button for each respective sector where you want to set the end of the sector. After configuring the sectors please follow the instructions that appear in the app to start your timings. Afterwards, in future sessions, the player can simply just drive if he/she has previously made a configuration for that track layout, resulting in a seamless gameplay loop after the configuration.


## Supported session types(both singleplayer and multiplayer):

- Practice
- Qualifying
- Hotlap
- Race

  
## Requirements

- at least version 2.2 of custom shaders patch (CSP)

- track has an implemented AI Line

- game must be live, not in a replay


The app will check by itself all these conditions when starting and will leave an appropriate message if a condition is not met.


## Notes regarding how the app works:

- sectors must be placed in a consecutive manner in terms of track progression, eg: sector 2 is placed at the end of the 5th corner, then sector 3 must be placed further ahead, for example at corner 7.
- can not place sectors in pit/pit lane
- changing the configuration of an already configured track will delete all the stored data about that track, including times for cars that you drove on the track.
- the app makes backups of the data file and stores the last 10 assetto corsa sessions. This feature is just in case you change a track configuration by mistake. If you want to restore a backup, simply go into the app's folder>data>backups and copy from there whatever backup you desire and paste it to app's folder>data and let it overwrite the current file.
- buttons will flash red to let you know that some conditions are not met. Such as trying to set a sector in pits or trying to set a sector while in a replay, would flash it red.


I highly suggest reading the User Manual PDF file, found inside the zip archive, to understand everything that the app offers.



## Update 1.4.2

- more intuitive UI, tells you why a button does not work now ( example: trying to reset the times outside pits will show a message to let you know why it does not work)
- completely rewritten the parts that manages session types,going to pits,resets and making sure the player is not in a replay.
- the program is now more robust, some leftover functionalities were encapsulated into separate methods so its easier to develop and debug
- tested all supported sessions in single and multiplayer
- fixed a bug where the app crashed due to a bad dictionary
- fixed a bug where the app wouldn't switch to the correct page
- fixed various bugs where the time wasn't recorded properly




## Update 1.4

- completely rewritten the app from 0, making it modular by using OOP and functional programming paradigms, easier to change/manage or add new functionalities
- added support for track layouts (meaning you can for example have separate configurations for nordschleife tourist while also having a configuration for nordschleife endurance)
- the program will make backups of the file that stores data about track config and car times, it will retain the latest 10 backups and delete backups older than that
- updated the app icon
- added exit/close buttons
- the dictionary that stores the data is now ordered, making it human-readable
- moved the ability to change the UI layout from the settings app to the main app
- can now directly set up the last sector to be equal to the finish line.
- can show your total time of all your sectors and your theoretical best lap time, by summing up the best times you have on every sector.
- works in all types of sessions now: practice, hotlap, time attack, race, track day, weekend, qualifying
- all app settings can now be changed from content manager's app tab
- the app has now a fully customizable opacity slider
- the auto next page function has now become on by default
- you can now change the delay until the app switches to the next page after clearing all the sectors on the current page
- you can store partial car times, example: you cleared 2 sectors out of 6, the program will now save the times for those 2 sectors, unlike in the previous version
where you had to go through all sectors for the car times to be saved
- the sector you're currently on is now colored in an orange color, instead of blue, since it was too hard to see before.
- fixed possible sim_info library conflict with other apps (there would be some cases where some apps would load into memory an older sim_info library after my app, resulting in errors
due to missing functions that were not available in those older versions)



## Contributions:
- Stereo - helping me with making the button function modular
- Nache - providing help in solving various logistic problems
- LeBluem - provided a solution to a possible version conflict of a third party library, when other apps use the same library, but with a different version


## Related docs:
- [Track Sectors User Manual.pdf](https://github.com/RuseCristian/Track-Sectors-Assetto-Corsa-App/files/10046798/Track.Sectors.User.Manual.pdf)


- [Technical Explainations.pdf](https://github.com/RuseCristian/Track-Sectors-Assetto-Corsa-App/files/10046803/Technical.Explainations.pdf)

