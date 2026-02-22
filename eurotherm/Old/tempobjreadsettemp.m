function setTemp = tempobjreadsettemp(serialObject)
% TEMPOBJREADSETTEMP Reads set temperature from Eurotherm controllers
% setTemp = tempobjreadsettemp(serialObject) Reads set point in °C from
% Eurotherm temperature controllers given an appropriate serial port object
% (generated from tempobj).

% e.g. setTemp = tempobjreadsettemp(tempobj(7)) - gives current set
% temperature from the device on COM7

% Range:

% serialObject = valid serial port object


% check the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information (tempobjcomm returns the temperature in °C)
setTemp = tempobjcomm('readfullres', serialObject, 1, 2, 1);