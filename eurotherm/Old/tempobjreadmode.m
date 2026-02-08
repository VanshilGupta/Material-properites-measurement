function mode = tempobjreadmode(serialObject)
% TEMPOBJREADMODE Reads the temperature mode from Eurotherm controllers
% mode = tempobjreadmode(serialObject) Reads operating mode from Eurotherm
% series 2000 temperature controllers given an appropriate serial port
% object (generated from tempobj).  Mode is 0 if auto, or 1 if manual.  Can
% also be 2 if "off" for 3000 series controllers.

% e.g. mode = tempobjreadmode(tempobj(7)) - returns 0 for auto from the
% device on COM7

% Range:

% serialObject = valid serial port object


% checks the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information
mode = tempobjcomm('read', serialObject, 1, 273, 1);