function maxTemp = tempobjreadmaxtemp(serialObject)
% TEMPOBJREADMAXTEMP Reads maximum temperature from Eurotherm controllers
% maxTemp = tempobjreadmaxtemp(serialObject) Reads maximum temperature in
% °C from Eurotherm temperature controllers given an appropriate serial
% port object (generated from tempobj).

% e.g. maxTemp = tempobjreadmaxtemp(tempobj(7)) - gives current maximum
% temperature from the device on COM7

% Range:

% serialObject = valid serial port object


% checks the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information (tempobjcomm returns the temperature in °C)
maxTemp = tempobjcomm('readfullres', serialObject, 1, 111, 1);