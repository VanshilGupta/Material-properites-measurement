function minTemp = tempobjreadmintemp(serialObject)
% TEMPOBJREADMINTEMP Reads minimum temperature from Eurotherm controllers
% minTemp = tempobjreadmintemp(serialObject) Reads minimum temperature in
% °C from Eurotherm temperature controllers given an appropriate serial
% port object (generated from tempobj).

% e.g. minTemp = tempobjreadmintemp(tempobj(7)) - gives current minimum
% temperature from the device on COM7

% Range:

% serialObject = valid serial port object


% checks the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information (tempobjcomm returns the temperature in °C)
minTemp = tempobjcomm('readfullres', serialObject, 1, 112, 1);