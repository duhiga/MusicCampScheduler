#VERY UNFINISHED
#his file contains fuctions to initiate empty databases needed for the rest of the app
from SQL import *

#the below creates 1 day worth of groups for meals
INSERT INTO `campq`.`groups` (`groupid`, `groupname`, `locationid`, `periodid`, `ismusical`, `iseveryone`) VALUES ('10', 'Breakfast', '2', '3', '0', '1');
INSERT INTO `campq`.`groups` (`groupid`, `groupname`, `locationid`, `periodid`, `ismusical`, `iseveryone`) VALUES ('11', 'Lunch', '2', '7', '0', '1');
INSERT INTO `campq`.`groups` (`groupid`, `groupname`, `locationid`, `periodid`, `ismusical`, `iseveryone`) VALUES ('12', 'Dinner', '2', '10', '0', '1');

#the below is 1 day worth of periods
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('21', '2016-12-31 07:30:00', '2016-05-17 09:00:00', 'Breakfast');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('22', '2016-12-31 08:00:00', '2016-05-17 09:00:00', 'Noisy Scrubs');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('23', '2016-12-31 09:00:00', '2016-05-17 10:15:00', 'Period 1');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('24', '2016-12-31 10:45:00', '2016-05-17 12:00:00', 'Period 2');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('25', '2016-12-31 12:00:00', '2016-05-17 13:00:00', 'Lunch');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('26', '2016-12-31 15:00:00', '2016-05-17 16:15:00', 'Period 3');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('27', '2016-12-31 16:15:00', '2016-05-17 17:30:00', 'Period 4');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('28', '2016-12-31 18:30:00', '2016-05-17 19:30:00', 'Dinner');
INSERT INTO `campq`.`periods` (`periodid`, `starttime`, `endtime`, `periodname`) VALUES ('29', '2016-12-31 19:30:00', '2016-11-17 21:00:00', 'Period 5');