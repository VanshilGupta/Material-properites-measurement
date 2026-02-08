function outputPower = tempobjreadoutputpower(serialObject)
% TEMPOBJREADOUTPUTPOWER Reads output power from Eurotherm controllers
% outputPower = tempobjreadoutputpower(serialObject) Reads output power (in
% %) from Eurotherm temperature controllers given an appropriate serial
% port object (generated from tempobj).

% e.g. outputPower = tempobjreadoutputpower(tempobj(7)) - gives current
% output power from the device on COM7, e.g. 100 for 100%.

% Range:

% serialObject = valid serial port object


% checks the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information
outputPower = tempobjcomm('readfullres', serialObject, 1, 3, 1);