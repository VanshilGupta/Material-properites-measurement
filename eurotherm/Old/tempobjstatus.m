function status = tempobjstatus(serialObject)
% TEMPOBJSTATUS Reads the status of the Eurotherm temperature controllers
% status = tempobjstatus(serialObject) Reads status from Eurotherm temperature
% controllers given an appropriate serial port object (generated from
% tempobj).  Status is 1 if the controller is running automatically
% (temperature is being regulated), or 0 if in manual mode.

% e.g. status = tempobjstatus(tempobj(7)) - gives current status from the
% device on COM7

% Range:

% serialObject = valid serial port object


% check the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information - it is 0 if it is in auto mode, so there is a '~'
status = ~tempobjcomm('read', serialObject, 1, 273, 1);