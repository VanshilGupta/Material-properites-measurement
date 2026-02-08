function mode = tempobjreadautotunemode(tempObj)
% TEMPOBJREADAUTOTUNEMODE Reads autotune mode from Eurotherm controllers
% mode = tempobjreadautotunemode(tempObj) Reads autotune mode from Eurotherm
% series 2000 temperature controllers given an appropriate serial port
% object (generated from tempobj).  Mode is 0 if off, or 1 if on.

% e.g. mode = tempobjreadautotunemode(tempobj(7)) - returns 0 for off from the
% device on COM7

% Range:

% tempObj = valid serial port object


% checks the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information
mode = tempobjcomm('read', tempObj, 1, 270, 1);