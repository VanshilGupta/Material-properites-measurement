function currentTemp = tempobjcurrenttemp(serialObject)
% TEMPOBJCURRENTTEMP Reads current temperature from Eurotherm controllers
% currentTemp = tempobjcurrenttemp(serialObject) Reads process variable
% (current temperature) in °C from Eurotherm temperature controllers given
% an appropriate serial port object (generated from tempobj).

% e.g. currentTemp = tempobjcurrentTemp(tempobj(7)) - gives current
% temperature from the device on COM7

% Range:

% serialObject = valid serial port object

% checks number of arguments
error(nargchk(1, 1, nargin))

% retrieves information (tempobjcomm returns the temperature in °C)
currentTemp = tempobjcomm('readfullres', serialObject, 1, 1, 1);

% if the current temperature says 1372 - its lying - its a sensor break
% - set it to NaN
if currentTemp == 1372
    % change it
    currentTemp = NaN;
end